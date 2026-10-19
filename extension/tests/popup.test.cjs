// Mocked browser/HTTP fixtures test UI behavior, not live evidence or model accuracy.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag = 'div') { this.tag = tag; this.children = []; this.handlers = {}; this.hidden = true; this.value = ''; this.disabled = false; this._text = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(' '); }
  set innerHTML(_) { throw new Error('Unsafe HTML insertion'); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  addEventListener(name, handler) { this.handlers[name] = handler; }
}

function setup(reportOverrides = {}, options = {}) {
  const nodes = new Map();
  for (const match of fs.readFileSync(path.join(__dirname,"../popup.html"),"utf8").matchAll(/id="([^"]+)"/g)) nodes.set(match[1],new Element());
  const employer = 'Legal Raasta Technologies Pvt. Ltd.';
  const page = { text: `About Careers\nCompany: ${employer}\nThis internship is remote.`, title: `Internship at ${employer}`, url: 'https://posting.example.com/job', originalLength: 130, truncated: false, structuredEmployer: employer };
  Object.assign(page, options.pageOverrides || {});
  const requests = [];
  const events = [];
  const report = { employer_name: employer, employer_extraction: 'user_supplied', normalized_employer: 'legal raasta technologies', verification_status: 'insufficient_evidence', status: 'no_sources', message: 'Insufficient employer-specific evidence retrieved.', sources_retrieved: [], supporting_evidence: [], unverified_claims: [], warnings: [], limitations: 'No factual verification is claimed.', search_queries: ['"Legal Raasta Technologies" careers'], excluded_sources: [{url:'https://careers.microsoft.com/',title:'Microsoft Careers Stage',stage:'search',reason:'Employer identity mismatch',entity_match:0}] };
  Object.assign(report, reportOverrides);
  const context = vm.createContext({ URL, AbortSignal, Set,
    document: {
      body: {innerText:page.text}, title:page.title,
      querySelectorAll: () => [{textContent:JSON.stringify({'@type':'JobPosting',hiringOrganization:{name:employer}})}],
      getElementById: id => { if (!nodes.has(id)) nodes.set(id,new Element()); return nodes.get(id); },
      createElement: tag => new Element(tag), createTextNode: text => {const node=new Element('text');node.textContent=text;return node;},
    },
    location: { origin:'https://posting.example.com', pathname:'/job' },
    chrome: {tabs:{query:async()=>[{id:1,url:page.url}]},scripting:{executeScript:async()=>{events.push("extract");return [{result:page}];}}},
    fetch: async(url, fetchOptions) => {
      requests.push({url,body:JSON.parse(fetchOptions.body)});
      if(url.endsWith('/analyze')) return {ok:true,json:async()=>({risk_level:'low',risk_score:0,summary:'Mock rule result',characters_analyzed:100,findings:[],disclaimer:'Mock rule note',ml_prediction:{status:'available',label:'legitimate',fraud_probability:0.2,note:'Mock ML fixture'},...(options.analysisOverrides || {})})};
      if(url.endsWith('/preview')) return {ok:true,json:async()=>({employer_name:employer,employer_extraction:'structured_job_posting'})};
      return {ok:true,json:async()=>report};
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../popup.js'),'utf8'),context);
  return {context,nodes,requests,employer,events};
}

test('extracts only JobPosting employer metadata alongside rendered text',()=>{
  const {context,employer}=setup();
  const page=vm.runInContext('extractPageText(50000)',context);
  assert.equal(page.structuredEmployer,employer);
  assert.match(page.text,/About Careers/);
});

test('scan keeps ML display, previews employer, resets stale overrides, and sends explicit correction',async()=>{
  const {nodes,requests,employer}=setup();
  nodes.get('employer-name').value='Stale company';
  await nodes.get('scan').handlers.click();
  assert.equal(nodes.get('employer-name').value,'');
  assert.equal(nodes.get('result').hidden,false);
  assert.match(nodes.get('ml-prediction').textContent,/Predicted legitimate/);
  assert.match(nodes.get('employer-preview').textContent,/Legal Raasta/);
  nodes.get('employer-name').value=employer;
  await nodes.get('investigate').handlers.click();
  const investigation=requests.find(request=>request.url.endsWith('/investigate'));
  assert.equal(investigation.body.employer_name,employer);
  assert.equal(investigation.body.structured_employer_name,employer);
  assert.match(nodes.get('investigation-report').textContent,/Insufficient employer-specific evidence retrieved/);
  assert.match(nodes.get('investigation-report').textContent,/Diagnostics: 1 excluded sources/);
  assert.match(nodes.get('investigation-report').textContent,/Microsoft Careers Stage/);
  assert.equal(nodes.get('scan').disabled,false);
});

test('unsafe evidence links are never made clickable',()=>{
  const {context}=setup();
  const link=vm.runInContext('safeSourceLink("javascript:alert(1)","test")',context);
  assert.equal(link.href,undefined);
});


test('renders valid Unicode passages and clean UI punctuation without reencoding',async()=>{
  const passage = "Legal Raasta Technologies offers internships \u2013 \u20b910,000 in \u0926\u093f\u0932\u094d\u0932\u0940. Caf\u00e9 \u00c2ngela \ud83d\ude00";
  const {nodes}=setup({supporting_evidence:[{claim_id:'claim-1',source_id:'source-1',url:'https://example.com/',excerpt:passage,cosine_similarity:0.5}]});
  await nodes.get('scan').handlers.click();
  await nodes.get('investigate').handlers.click();
  assert.ok(nodes.get('investigation-report').textContent.includes(passage));
  assert.match(nodes.get('coverage').textContent,/\u00b7 Top frame only/);
  assert.ok(!nodes.get('ml-prediction').textContent.includes('\u00c2\u00b7'));
  assert.ok(!nodes.get('investigation-report').textContent.includes('\u00e2\u20ac\u201c'));
  const source=fs.readFileSync(path.join(__dirname,'../popup.js'),'utf8');
  assert.ok(!source.includes('\u00c2\u00b7') && !source.includes('\u00e2\u20ac\u00a6'));
});


test('renders independent domain/email findings and deterministic advisory',async()=>{
  const additions={
    job_information:{job_title:'Engineering Intern',employer_name:'Acme Robotics',current_website:'https://acmerob0tics.com/job',analyzed_at:'2026-10-19T12:00:00Z'},
    advisory:{category:'Elevated warning indicators',reasons:['A controlled lookalike indicator was detected.'],recommendation:'Independently verify the recruiter domain.'},
    domain_analysis:{hostname:'acmerob0tics.com',registered_domain:'acmerob0tics.com',established_employer_domains:['acmerobotics.com'],establishment_basis:'Controlled operator record',message:'Potential lookalike indicator.',limitations:'Not a fraud verdict.',findings:[{code:'character_substitution',severity:'high',explanation:'Common character substitution.',observed_domain:'acmerob0tics.com',compared_domain:'acmerobotics.com'}]},
    email_analysis:{message:'Assessed 1 recruitment email.',emails:[{address:'jobs@acmerob0tics.com',email_domain:'acmerob0tics.com',registered_domain:'acmerob0tics.com',established_employer_domains:['acmerobotics.com'],assessment:'potential_impersonation',explanation:'Check independently.',findings:[]}],scope_note:'No mail is sent.'}
  };
  const {nodes}=setup({}, {analysisOverrides:additions});
  await nodes.get('scan').handlers.click();
  assert.match(nodes.get('job-details').textContent,/Acme Robotics/);
  assert.equal(nodes.get('risk').textContent,'Elevated warning indicators');
  assert.match(nodes.get('domain-analysis').textContent,/acmerob0tics.com/);
  assert.match(nodes.get('domain-analysis').textContent,/acmerobotics.com/);
  assert.match(nodes.get('email-analysis').textContent,/jobs@acmerob0tics.com/);
  assert.equal(nodes.get('recommendation').textContent,'Independently verify the recruiter domain.');
});

test('blocks private browser interfaces before reading page content',async()=>{
  const {nodes,events,requests}=setup({}, {pageOverrides:{url:'https://mail.google.com/mail/u/0/'}});
  await nodes.get('scan').handlers.click();
  assert.equal(events.length,0);
  assert.equal(requests.length,0);
  assert.match(nodes.get('status').textContent,/Private mail/);
});

test('all eight dashboard sections exist and URLs remain clickable safely',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../popup.html'),'utf8');
  assert.equal([...html.matchAll(/class="section-number"/g)].length,8);
  const {context}=setup();
  const link=vm.runInContext('safeSourceLink("https://example.com/evidence", "Evidence")',context);
  assert.equal(link.href,'https://example.com/evidence');
  assert.equal(link.rel,'noopener noreferrer');
});
