from django.test import RequestFactory, TestCase

from model_mommy import mommy

from hmda.models.pages import HmdaHistoricDataPage


class TestHmdaHistoricDataPage(TestCase):
    data_years = ['2017', '2016', '2015', '2014', '2013', '2012',
                  '2011', '2010', '2009', '2008', '2007']

    def setUp(self):
        self.factory = RequestFactory()

    def test_hmda_explorer_page_no_params(self):
        page = mommy.prepare(HmdaHistoricDataPage)
        test_context = page.get_context(self.factory.get('/'))

        self.assertEqual(test_context['title'], 'Showing nationwide records')
        self.assertEqual(test_context['subtitle'],
            'Originated mortgages for first lien, owner-occupied, 1-4 family homes')  # noqa E501
        # self.assertEqual(test_context['files'].keys(), self.data_years)

    def test_hmda_explorer_page_with_params(self):
        page = mommy.prepare(HmdaHistoricDataPage)
        request = '/?geo=ny&records=all-records&field_descriptions=codes'
        test_context = page.get_context(self.factory.get(request))

        self.assertEqual(test_context['title'], 'Showing records for New York')
        self.assertEqual(test_context['subtitle'], 'All records')
        self.assertEqual(test_context['files'].keys(), self.data_years)
