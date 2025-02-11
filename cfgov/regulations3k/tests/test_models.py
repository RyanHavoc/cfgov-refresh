from __future__ import unicode_literals

import datetime
import sys
import unittest

# from django.core.urlresolvers import reverse
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, QueryDict  # Http404, HttpResponse
from django.test import RequestFactory, TestCase as DjangoTestCase

from wagtail.wagtailcore.models import Site

import mock
from model_mommy import mommy

from regulations3k.models.django import (
    EffectiveVersion, Part, Section, SectionParagraph, Subpart, sortable_label
)
from regulations3k.models.pages import (
    RegulationLandingPage, RegulationPage, RegulationsSearchPage,
    get_next_section, get_previous_section, get_secondary_nav_items,
    get_section_url, validate_num_results, validate_page_number
)


class RegModelTests(DjangoTestCase):
    def setUp(self):
        from v1.models import HomePage
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            username='supertest', password='test', email='test@email.com'
        )

        self.site = Site.objects.get(is_default_site=True)

        self.ROOT_PAGE = HomePage.objects.get(slug='cfgov')
        self.landing_page = RegulationLandingPage(
            title='Reg Landing', slug='reg-landing')
        self.ROOT_PAGE.add_child(instance=self.landing_page)

        self.part_1002 = mommy.make(
            Part,
            part_number='1002',
            title='Equal Credit Opportunity Act',
            letter_code='B',
            chapter='X'
        )
        self.part_1030 = mommy.make(
            Part,
            part_number='1030',
            title='Truth In Savings',
            letter_code='DD', chapter='X'
        )
        self.effective_version = mommy.make(
            EffectiveVersion,
            effective_date=datetime.date(2014, 1, 18),
            part=self.part_1002
        )
        self.old_effective_version = mommy.make(
            EffectiveVersion,
            effective_date=datetime.date(2011, 1, 1),
            part=self.part_1002,
        )
        self.draft_effective_version = mommy.make(
            EffectiveVersion,
            effective_date=datetime.date(2020, 1, 1),
            part=self.part_1002,
            draft=True,
        )
        self.subpart = mommy.make(
            Subpart,
            label='Subpart General',
            title='Subpart A - General',
            subpart_type=Subpart.BODY,
            version=self.effective_version
        )
        self.subpart_appendices = mommy.make(
            Subpart,
            label='Appendices',
            title='Appendices',
            subpart_type=Subpart.APPENDIX,
            version=self.effective_version
        )
        self.subpart_interps = mommy.make(
            Subpart,
            label='Official Interpretations',
            title='Supplement I to Part 1002',
            subpart_type=Subpart.INTERPRETATION,
            version=self.effective_version
        )
        self.subpart_orphan = mommy.make(
            Subpart,
            label='General Mistake',
            title='An orphan subpart with no sections for testing',
            version=self.effective_version
        )
        self.old_subpart = mommy.make(
            Subpart,
            label='Subpart General',
            title='General',
            subpart_type=Subpart.BODY,
            version=self.old_effective_version
        )
        self.section_num4 = mommy.make(
            Section,
            label='4',
            title='\xa7\xa01002.4 General rules.',
            contents=(
                '{a}\n(a) Regdown paragraph a.\n'
                '{b}\n(b) Paragraph b\n'
                '\nsee(4-b-Interp)\n'
                '{c}\n(c) Paragraph c.\n'
                '{c-1}\n \n'
                '{d}\n(1) General rule. A creditor that provides in writing.\n'
            ),
            subpart=self.subpart,
        )
        self.graph_to_keep = mommy.make(
            SectionParagraph,
            section=self.section_num4,
            paragraph_id='d',
            paragraph=(
                '(1) General rule. A creditor that provides in writing.')
        )
        self.graph_to_delete = mommy.make(
            SectionParagraph,
            section=self.section_num4,
            paragraph_id='x',
            paragraph='(x) Non-existent graph that should get deleted.'
        )
        self.section_num15 = mommy.make(
            Section,
            label='15',
            title='\xa7\xa01002.15 Rules concerning requests for information.',
            contents='regdown content.',
            subpart=self.subpart,
        )
        self.section_alpha = mommy.make(
            Section,
            label='A',
            title=('Appendix A to Part 1002-Federal Agencies '
                   'To Be Listed in Adverse Action Notices'),
            contents='regdown content.',
            subpart=self.subpart_appendices,
        )
        self.section_beta = mommy.make(
            Section,
            label='B',
            title=('Appendix B to Part 1002-Errata'),
            contents='regdown content.',
            subpart=self.subpart_appendices,
        )
        self.section_interps = mommy.make(
            Section,
            label='Interp-A',
            title=('Official interpretations for Appendix A to Part 1002'),
            contents='interp content.',
            subpart=self.subpart_interps,
        )
        self.old_section_num4 = mommy.make(
            Section,
            label='4',
            title='\xa7\xa01002.4 General rules.',
            contents='regdown contents',
            subpart=self.old_subpart,
        )

        self.reg_page = RegulationPage(
            regulation=self.part_1002,
            title='Reg B',
            slug='1002')

        self.reg_search_page = RegulationsSearchPage(
            title="Search regulations",
            slug='search-regulations')

        self.landing_page.add_child(instance=self.reg_page)
        self.landing_page.add_child(instance=self.reg_search_page)
        self.reg_page.save()
        self.reg_search_page.save()

    def get_request(self, path='', data={}):
        request = self.factory.get(path, data=data)
        request.site = self.site
        return request

    def test_part_string_method(self):
        self.assertEqual(
            self.part_1002.__str__(),
            '12 CFR Part 1002 (Regulation B)'
        )

    def test_part_cfr_title_method(self):
        part = self.part_1002
        self.assertEqual(
            part.cfr_title,
            "{} CFR Part {} (Regulation {})".format(
                part.cfr_title_number,
                part.part_number,
                part.letter_code))

    def test_subpart_string_method(self):
        self.assertEqual(
            self.subpart.__str__(),
            'Subpart A - General')

    def test_section_string_method(self):
        if sys.version_info >= (3, 0):  # pragma: no cover
            self.assertEqual(
                self.section_num4.__str__(),
                '\xa7\xa01002.4 General rules.')
        else:  # pragma: no cover
            self.assertEqual(
                self.section_num4.__str__(),
                '\xa7\xa01002.4 General rules.'.encode('utf8'))

    def test_section_export_graphs(self):
        test_counts = self.section_num4.extract_graphs()
        self.assertEqual(test_counts['section'], "1002-4")
        self.assertEqual(test_counts['created'], 4)
        self.assertEqual(test_counts['deleted'], 1)
        self.assertEqual(test_counts['kept'], 1)

    def test_section_paragraph_str(self):
        self.assertEqual(
            self.graph_to_keep.__str__(),
            "Section 1002-4 paragraph d")

    def test_subpart_headings(self):
        for each in Subpart.objects.all():
            self.assertEqual(each.subpart_heading, '')

    def test_effective_version_string_method(self):
        self.assertEqual(
            self.effective_version.__str__(),
            'Effective on 2014-01-18')

    def test_live_version_true(self):
        self.assertTrue(self.effective_version.live_version)

    def test_status_is_live(self):
        self.assertEqual(self.effective_version.status, 'LIVE')

    def test_status_is_draft(self):
        self.effective_version.draft = True
        self.effective_version.save()
        self.assertEqual(self.effective_version.status, 'Unapproved draft')
        self.effective_version.draft = False
        self.effective_version.effective_date = (
            datetime.datetime.today().date() + datetime.timedelta(days=5))
        self.effective_version.save()
        self.assertEqual(self.effective_version.status, 'Future version')
        self.effective_version.effective_date = datetime.date(2014, 1, 18)
        self.effective_version.save()

    def test_status_is_previous_version(self):
        self.assertEqual(self.old_effective_version.status, 'Previous version')

    def test_landing_page_get_context(self):
        test_context = self.landing_page.get_context(self.get_request())
        self.assertIn('get_secondary_nav_items', test_context)

    def test_search_page_get_template(self):
        self.assertEqual(
            self.reg_search_page.get_template(self.get_request()),
            'regulations3k/search-regulations.html')

    def test_search_results_page_get_template(self):
        request = self.get_request(data={'partial': 'true'})
        self.assertEqual(
            self.reg_search_page.get_template(request),
            'regulations3k/search-regulations-results.html')
        # Should return partial results even if no value is provided
        request = self.get_request(data={'partial': ''})
        self.assertEqual(
            self.reg_search_page.get_template(request),
            'regulations3k/search-regulations-results.html')

    def test_routable_reg_page_get_context(self):
        test_context = self.reg_page.get_context(self.get_request())
        self.assertEqual(
            test_context['regulation'],
            self.reg_page.regulation)

    def test_get_secondary_nav_items(self):
        request = self.get_request()
        request.path = '/regulations/1002/4/'
        sections = list(self.reg_page.get_section_query().all())
        test_nav_items = get_secondary_nav_items(
            request, self.reg_page, sections
        )[0]
        self.assertEqual(
            len(test_nav_items),
            Subpart.objects.filter(
                version=self.effective_version
            ).exclude(
                sections=None
            ).count()
        )

    def test_get_section_url(self):
        url = get_section_url(self.reg_page, self.section_num4)
        self.assertEqual(url, '/reg-landing/1002/4/')

    def test_get_section_url_no_section(self):
        url = get_section_url(self.reg_page, None)
        self.assertIsNone(url)

    def test_section_page_view(self):
        response = self.client.get('/reg-landing/1002/4/')
        self.assertEqual(response.status_code, 200)

    def test_section_page_view_section_does_not_exist(self):
        response = self.client.get('/reg-landing/1002/82/')
        self.assertRedirects(
            response,
            '/reg-landing/1002/',
            fetch_redirect_response=False
        )

    def test_section_page_view_section_does_not_exist_with_date(self):
        response = self.client.get('/reg-landing/1002/2011-01-01/82/')
        self.assertRedirects(
            response,
            '/reg-landing/1002/2011-01-01/',
            fetch_redirect_response=False
        )

    def test_sortable_label(self):
        self.assertEqual(sortable_label('1-A-Interp'), ('0001', 'A', 'interp'))

    def test_render_interp(self):
        result = self.reg_page.render_interp({}, 'some contents')
        self.assertIn('some contents', result)

    def test_render_interp_with_title(self):
        result = self.reg_page.render_interp(
            {},
            '# A title\n\nsome contents'
        )
        self.assertIn('Official interpretation of A title', result)
        self.assertIn('some contents', result)

    def test_section_ranges(self):
        self.assertEqual(self.subpart_orphan.section_range, '')
        self.assertEqual(self.subpart_appendices.section_range, '')
        self.assertEqual(self.subpart_interps.section_range, '')
        self.assertEqual(
            self.subpart.section_range,
            '\xa7\xa01002.4\u2013\xa7\xa01002.15')

    def test_section_title_content(self):
        self.assertEqual(
            self.section_num15.title_content,
            'Rules concerning requests for information.')

    def test_section_part(self):
        self.assertEqual(self.section_num4.part, '1002')

    def test_section_section_number(self):
        self.assertEqual(self.section_num4.section_number, '4')

    def test_section_numeric_label(self):
        self.assertEqual(self.section_num4.numeric_label, '\xa7\xa01002.4')

    def test_section_numeric_label_not_digits(self):
        self.assertEqual(self.section_alpha.numeric_label, '')

    def test_section_title_content_not_digits(self):
        self.assertEqual(
            self.section_beta.title_content,
            'Appendix B to Part 1002-Errata'
        )

    @mock.patch('regulations3k.models.pages.SearchQuerySet.models')
    def test_routable_search_page_calls_elasticsearch(self, mock_sqs):
        mock_return = mock.Mock()
        mock_return.part = '1002'
        mock_return.text = ('Now is the time for all good men to come to the '
                            'aid of their country.')
        mock_return.highlighted = ['Now is the time for all good men',
                                   'to come to the aid of their country.']
        mock_return.paragraph_id = 'a'
        mock_return.title = 'Section 1002.1 Now is the time.'
        mock_return.section_label = '1'
        mock_queryset = mock.Mock()
        mock_queryset.__iter__ = mock.Mock(return_value=iter([mock_return]))
        mock_queryset.count.return_value = 1
        mock_sqs.return_value = mock_queryset
        response = self.client.get(
            self.reg_search_page.url + self.reg_search_page.reverse_subpage(
                'regulation_results_page'),
            {'q': 'disclosure', 'regs': '1002', 'order': 'regulation'})
        self.assertEqual(mock_sqs.call_count, 3)
        self.assertEqual(response.status_code, 200)
        response2 = self.client.get(
            self.reg_search_page.url + self.reg_search_page.reverse_subpage(
                'regulation_results_page'),
            QueryDict(query_string=(
                'q=disclosure&regs=1002&regs=1003&order=regulation')))
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(mock_sqs.call_count, 6)

    @mock.patch('regulations3k.models.pages.SearchQuerySet.models')
    def test_routable_search_page_handles_null_highlights(self, mock_sqs):
        mock_return = mock.Mock()
        mock_return.part = '1002'
        mock_return.text = ''
        mock_return.highlighted = None
        mock_return.paragraph_id = 'a'
        mock_return.title = 'Section 1002.1 Now is the time.'
        mock_return.section_label = '1'
        mock_queryset = mock.Mock()
        mock_queryset.__iter__ = mock.Mock(return_value=iter([mock_return]))
        mock_queryset.count.return_value = 1
        mock_sqs.return_value = mock_queryset
        response = self.client.get(
            self.reg_search_page.url + self.reg_search_page.reverse_subpage(
                'regulation_results_page'),
            {'q': 'disclosure', 'regs': '1002', 'order': 'regulation'})
        self.assertEqual(mock_sqs.call_count, 3)
        self.assertEqual(response.status_code, 200)
        response2 = self.client.get(
            self.reg_search_page.url + self.reg_search_page.reverse_subpage(
                'regulation_results_page'),
            QueryDict(query_string=(
                'q=disclosure&regs=1002&regs=1003&order=regulation')))
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(mock_sqs.call_count, 6)

    @mock.patch('regulations3k.models.pages.SearchQuerySet.models')
    def test_search_page_refuses_single_character_search(self, mock_sqs):
        response = self.client.get(
            self.reg_search_page.url + self.reg_search_page.reverse_subpage(
                'regulation_results_page'),
            {'q': '%21', 'regs': '1002', 'order': 'regulation'})
        self.assertEqual(mock_sqs.call_count, 0)
        self.assertEqual(response.status_code, 200)

    @mock.patch('regulations3k.models.pages.SearchQuerySet.models')
    def test_routable_search_page_reg_only(self, mock_sqs):
        response = self.client.get(
            self.reg_search_page.url + self.reg_search_page.reverse_subpage(
                'regulation_results_page'),
            QueryDict(query_string='regs=1002'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_sqs.call_count, 0)

    def test_get_breadcrumbs_section(self):
        crumbs = self.reg_page.get_breadcrumbs(
            self.get_request(),
            section=self.section_num4
        )
        self.assertEqual(
            crumbs,
            [
                {
                    'href': '/reg-landing/1002/',
                    'title': '12 CFR Part 1002 (Regulation B)'
                },
            ]
        )

    @mock.patch('regulations3k.models.pages.requests.get')
    def test_landing_page_recent_notices(self, mock_requests_get):
        mock_response = mock.Mock()
        mock_response.json.return_value = {'some': 'json'}
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response
        response = self.client.get(
            self.landing_page.url +
            self.landing_page.reverse_subpage('recent_notices')
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"some": "json"}')

    @mock.patch('regulations3k.models.pages.requests.get')
    def test_landing_page_recent_notices_error(self, mock_requests_get):
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_requests_get.return_value = mock_response
        response = self.client.get(
            self.landing_page.url +
            self.landing_page.reverse_subpage('recent_notices')
        )
        self.assertEqual(response.status_code, 500)

    def test_get_effective_version_not_draft(self):
        request = self.get_request()
        effective_version = self.reg_page.get_effective_version(
            request, '2014-01-18'
        )
        self.assertEqual(effective_version, self.effective_version)

    def test_get_effective_version_draft_with_perm(self):
        request = self.get_request()
        request.user = self.superuser
        effective_version = self.reg_page.get_effective_version(
            request, '2020-01-01'
        )
        self.assertEqual(effective_version, self.draft_effective_version)

    def test_get_effective_version_draft_without_perm(self):
        request = self.get_request()
        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            self.reg_page.get_effective_version(
                request, '2020-01-01'
            )

    def test_index_page_with_effective_date(self):
        response = self.client.get('/reg-landing/1002/2011-01-01/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'This version is not the current regulation',
                      response.content)
        self.assertIn(b'Jan. 1, 2011', response.content)

    def test_index_page_without_effective_date(self):
        response = self.client.get('/reg-landing/1002/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Most recently amended Jan. 18, 2014', response.content)

    def test_section_page_with_effective_date(self):
        response = self.client.get('/reg-landing/1002/2011-01-01/4/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'This version is not the current regulation',
                      response.content)

    def test_section_page_without_effective_date(self):
        response = self.client.get('/reg-landing/1002/4/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'This version is the current regulation',
                      response.content)
        self.assertIn(b'Search this regulation', response.content)

    def test_versions_page_view_without_section(self):
        response = self.client.get('/reg-landing/1002/versions/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Jan. 18, 2014', response.content)
        self.assertIn(b'(current regulation)', response.content)
        self.assertIn(b'Jan. 1, 2011', response.content)
        self.assertNotIn(b'Jan. 1, 2020', response.content)

    def test_versions_page_view_with_section(self):
        response = self.client.get('/reg-landing/1002/versions/4/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b'href="/reg-landing/1002/2011-01-01/4/"',
            response.content
        )

    def test_get_breadcrumbs_section_with_date(self):
        crumbs = self.reg_page.get_breadcrumbs(
            self.get_request(),
            section=self.section_num4,
            date_str='2011-01-01'
        )
        self.assertEqual(
            crumbs,
            [
                {
                    'href': '/reg-landing/1002/2011-01-01/',
                    'title': '12 CFR Part 1002 (Regulation B)'
                },
            ]
        )

    def test_effective_version_date_unique(self):
        new_effective_version = mommy.make(
            EffectiveVersion,
            effective_date=datetime.date(2020, 1, 1),
            part=self.part_1002,
            draft=True,
        )
        with self.assertRaises(ValidationError):
            new_effective_version.validate_unique()


class SectionNavTests(unittest.TestCase):

    def test_get_next_section(self):
        section_list = ['1002.1', '1002.2']
        current_index = 0
        self.assertEqual(
            get_next_section(section_list, current_index), '1002.2')

    def test_get_next_section_none(self):
        section_list = ['1002.1', '1002.2']
        current_index = 1
        self.assertIs(
            get_next_section(section_list, current_index), None)

    def test_get_previous_section(self):
        section_list = ['1002.1', '1002.2']
        current_index = 1
        self.assertEqual(
            get_previous_section(section_list, current_index), '1002.1')

    def test_get_previous_section_none(self):
        section_list = ['1002.1', '1002.2']
        current_index = 0
        self.assertIs(
            get_previous_section(section_list, current_index), None)

    def test_validate_page_number(self):
        paginator = Paginator([{'fake': 'results'}] * 30, 25)
        request = HttpRequest()
        self.assertEqual(validate_page_number(request, paginator), 1)
        request.GET.update({'page': '2'})
        self.assertEqual(validate_page_number(request, paginator), 2)
        request = HttpRequest()
        request.GET.update({'page': '1000'})
        self.assertEqual(validate_page_number(request, paginator), 1)
        request = HttpRequest()
        request.GET.update({'page': '<script>Boo</script>'})
        self.assertEqual(validate_page_number(request, paginator), 1)

    def test_validate_num_results(self):
        request = HttpRequest()
        self.assertEqual(validate_num_results(request), 25)
        request.GET.update({'results': '50'})
        self.assertEqual(validate_num_results(request), 50)
        request = HttpRequest()
        request.GET.update({'results': '100'})
        self.assertEqual(validate_num_results(request), 100)
        request = HttpRequest()
        request.GET.update({'results': '25'})
        self.assertEqual(validate_num_results(request), 25)
        request = HttpRequest()
        request.GET.update({'results': '<script>'})
        self.assertEqual(validate_num_results(request), 25)
        request = HttpRequest()
        request.GET.update({'results': '10'})
        self.assertEqual(validate_num_results(request), 25)
