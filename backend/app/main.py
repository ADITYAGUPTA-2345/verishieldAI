import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request

from .config import MODEL_PATH

from .analyzer import analyze
from .schemas import AnalyzeRequest, AnalyzeResponse, MLPrediction
from . import config
from .investigation.schemas import InvestigateRequest, InvestigationReport
from .investigation.service import investigate, investigation_context
from .investigation.tinyfish import TinyFishClient
from .security.assessment import attach_assessments
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.investigation_limiter = asyncio.Semaphore(2)
    app.state.predictor = None
    app.state.model_note = "Model artifact missing. Run python -m ml.train and restart the backend."
    if MODEL_PATH.is_file():
        try:
            from ml.inference import ModelPredictor
            app.state.predictor = ModelPredictor(MODEL_PATH)
        except Exception:
            logger.exception("Could not load trusted local model artifact")
            app.state.model_note = "Model artifact could not be loaded. Check server logs and retrain."
    yield
    app.state.predictor = None


app = FastAPI(title="VeriShield AI", version="0.3.0", lifespan=lifespan,
              description="Local rules and ML, with separately requested TinyFish employer investigations")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "verishield-ai"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_posting(request: AnalyzeRequest, http_request: Request) -> AnalyzeResponse:
    # URL is context only; page text is not logged or sent externally by this route.
    result = analyze(request.text)
    predictor = getattr(http_request.app.state, "predictor", None)
    if predictor is None:
        result.ml_prediction = MLPrediction(note=getattr(http_request.app.state, "model_note", "Model not loaded. Restart the backend."))
    else:
        try:
            # Same combined plain-text representation as training, without URL metadata.
            text = "\n".join(filter(None, [request.title, request.text]))
            result.ml_prediction = MLPrediction(**predictor.predict(text))
        except Exception:
            logger.exception("Local model inference failed")
            result.ml_prediction = MLPrediction(note="Model inference failed. Rule findings remain available; check server logs.")
    return attach_assessments(result, request)



def get_tinyfish_client() -> TinyFishClient:
    return TinyFishClient(config.TINYFISH_API_KEY)


@app.post("/investigate/preview")
def preview_investigation(request: InvestigateRequest) -> dict:
    """No web request: show the chosen identity and queries before investigating."""
    return investigation_context(request)


@app.post("/investigate", response_model=InvestigationReport)
async def investigate_employer(request: InvestigateRequest, http_request: Request,
                               client: TinyFishClient = Depends(get_tinyfish_client)) -> InvestigationReport:
    limiter = getattr(http_request.app.state, "investigation_limiter", None)
    if limiter is None:
        report = await investigate(request, client)
    else:
        try:
            await asyncio.wait_for(limiter.acquire(), timeout=0.1)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=429, detail="Two investigations are already running. Retry shortly.") from None
        try:
            report = await investigate(request, client)
        finally:
            limiter.release()
    # Reuse existing fetched sources. Local classifier is re-used without fitting
    # or any extra TinyFish call; CPU work stays off the async event loop.
    def enrich():
        local = analyze_posting(request, http_request)
        attach_assessments(local, request, report)
        report.domain_analysis = local.domain_analysis
        report.email_analysis = local.email_analysis
        report.advisory = local.advisory
        report.job_information = local.job_information
        return report
    return await run_in_threadpool(enrich)
