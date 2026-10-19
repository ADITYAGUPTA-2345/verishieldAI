"""Offline fixtures only; no emails are sent and domains are not resolved."""
import pytest

from backend.app.security.emails import analyze_emails, assess_email

OFFICIAL = ['acmerobotics.com']


def test_matching_email_and_subdomain_namespace():
    assert assess_email('HR@ACMEROBOTICS.COM','Acme Robotics',OFFICIAL).assessment == 'domain_match'
    result = assess_email('jobs@talent.acmerobotics.com','Acme Robotics',OFFICIAL)
    assert result.assessment == 'organizational_subdomain'
    assert 'not verified' in result.explanation


def test_lookalike_and_misleading_email_domains():
    for address in ['recruitment@acmerob0tics.com','jobs@acmerobotics-careers-example.com','hr@acmerobotics.com.fakejobs.org']:
        result = assess_email(address,'Acme Robotics',OFFICIAL)
        assert result.assessment == 'potential_impersonation'
        assert any(f.severity in {'medium','high'} for f in result.findings)


@pytest.mark.parametrize('domain',['gmail.com','outlook.com','yahoo.com','proton.me'])
def test_public_provider_is_not_automatic_fraud(domain):
    result = assess_email('recruiter@'+domain,'Acme Robotics',OFFICIAL)
    assert result.assessment == 'public_provider'
    assert all(f.severity == 'info' for f in result.findings)


def test_unknown_official_and_no_email():
    assert assess_email('jobs@acmerobotics.com','Acme Robotics',[]).assessment == 'unverified_domain'
    result = analyze_emails('A role with no contact address.',None,'Acme Robotics',OFFICIAL)
    assert result.message == 'No recruitment email detected.'
    assert not result.emails


def test_only_recruitment_context_is_extracted():
    text = ('Signed in as applicant@gmail.com\nYour account email: jobs@gmail.com\n'
            'Contact us: support@jobboard.com\nApply by sending your CV to hiring@acmerobotics.com\n'
            'Salary Search: Email jobs@unrelated.com\nRelated jobs\nApply at hr@other-employer.com')
    result = analyze_emails(text,'https://example.com/job','Acme Robotics',OFFICIAL)
    assert [email.address for email in result.emails] == ['hiring@acmerobotics.com']


def test_labeled_contact_in_job_description_is_allowed_and_deduplicated():
    text = 'Job description\nEmail: alice@acmerobotics.com\nApply to alice@ACMEROBOTICS.COM'
    result = analyze_emails(text,None,'Acme Robotics',OFFICIAL)
    assert len(result.emails) == 1
    assert result.emails[0].assessment == 'domain_match'


def test_private_interfaces_are_not_email_sources():
    for url in ['https://mail.google.com/mail/u/0/','https://linkedin.com/messaging/thread','https://example.com/account/settings']:
        result = analyze_emails('Recruitment email: hr@gmail.com',url,'Acme Robotics',OFFICIAL)
        assert not result.emails
        assert 'skipped' in result.scope_note


def test_ordinary_third_party_domain_is_not_accused_of_fraud():
    result = assess_email('recruiter@staffing-agency.com','Acme Robotics',OFFICIAL)
    assert result.assessment == 'different_domain'
    assert all(f.severity in {'low','info'} for f in result.findings)
