from django.test import TestCase
from mock import Mock, patch

from datetime import date
import json

from scripts import unpublish_closed_jobs

from v1.tests.wagtail_pages import helpers

from jobmanager.models.django import ApplicantType, JobCategory, Region
from jobmanager.models.pages import JobListingPage
from jobmanager.models.panels import USAJobsApplicationLink

CLOSED_HTML = (
    '<html>'
    '<div class="usajobs-joa-closed">'
    'This job announcement has closed'
    '</div>'
    '</html>'
)


class UnpublishClosedJobsTestCase(TestCase):
    def setUp(self):
        division = JobCategory(
            job_category="category"
        )
        division.save()
        region = Region(
            abbreviation="TS",
            name="TriStateArea"
        )
        region.save()
        self.applicant_type = ApplicantType(
            applicant_type="applicant",
            description="description"
        )
        self.applicant_type.save()
        self.page = JobListingPage(
            title='title1',
            salary_min='1',
            salary_max='2',
            description='description',
            open_date=date(2099, 1, 1),
            close_date=date(2099, 1, 15),
            division=division,
            location=region,
            live=True)
        helpers.publish_page(child=self.page)

    def create_job_link(self, control_number):
        job_link = USAJobsApplicationLink(
            announcement_number=control_number,
            applicant_type=self.applicant_type,
            url='http://www.test.com/{}'.format(control_number),
            job_listing=self.page
        )
        job_link.save()
        return job_link

    def api_closed_job_response(self, control_number):
        mock_response = Mock()
        mock_response.status_code = 200
        text = {
            "SearchResult": {
                "SearchResultItems": [
                    {"MatchedObjectId": control_number}
                ]
            }
        }
        mock_response.text = json.dumps(text)
        return mock_response

    @patch('requests.get', return_value={})
    @patch('urllib2.urlopen', return_value='')
    def test_job_listing_page_still_live_if_job_not_closed(
            self, page_check, api_check):
        self.assertTrue(self.page.live)

        control_number = '1'
        job_link = self.create_job_link(control_number)
        unpublish_closed_jobs.run()
        self.page.refresh_from_db()

        page_check.assert_called_once_with(job_link.url)
        args, kwargs = api_check.call_args
        self.assertEqual(
            kwargs['params'],
            {'ControlNumber': control_number, 'WhoMayApply': 'all'}
        )
        self.assertTrue(self.page.live)
        self.assertFalse(self.page.expired)

    @patch('requests.get', return_value={})
    @patch('urllib2.urlopen', return_value=CLOSED_HTML)
    def test_job_listing_page_unpublished_if_job_closed_on_usajobs(
            self, page_check, api_check):
        self.assertTrue(self.page.live)
        control_number = '1'

        job_link = self.create_job_link(control_number)
        unpublish_closed_jobs.run()
        self.page.refresh_from_db()

        page_check.assert_called_once_with(job_link.url)
        self.assertFalse(self.page.live)
        self.assertTrue(self.page.expired)

    @patch('requests.get')
    @patch('urllib2.urlopen', return_value='')
    def test_job_listing_page_unpublished_if_job_archived(
            self, page_check, api_check):
        self.assertTrue(self.page.live)
        control_number = '1'

        self.create_job_link(control_number)
        api_check.return_value = self.api_closed_job_response(control_number)

        unpublish_closed_jobs.run()
        self.page.refresh_from_db()

        self.assertFalse(self.page.live)
        self.assertTrue(self.page.expired)

    @patch('requests.get')
    @patch('urllib2.urlopen', return_value='')
    def test_job_listing_page_live_if_only_1_of_2_links_closed(
            self, page_check, api_check):
        self.assertTrue(self.page.live)
        self.create_job_link('1')
        self.create_job_link('2')
        api_check.side_effect = [self.api_closed_job_response('1'), None]

        unpublish_closed_jobs.run()
        self.page.refresh_from_db()

        self.assertTrue(self.page.live)
        self.assertFalse(self.page.expired)

    @patch('requests.get')
    @patch('urllib2.urlopen', return_value='')
    def test_job_listing_page_unpublished_if_all_links_closed(
            self, page_check, api_check):
        self.assertTrue(self.page.live)
        self.create_job_link('1')
        self.create_job_link('2')
        api_check.side_effect = [
            self.api_closed_job_response('1'),
            self.api_closed_job_response('2')
        ]
        unpublish_closed_jobs.run()
        self.page.refresh_from_db()
        self.assertFalse(self.page.live)
        self.assertTrue(self.page.expired)
