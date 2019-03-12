from __future__ import unicode_literals

import csv
import json
import os

from django.conf import settings
from django.contrib.auth.models import User

from ask_cfpb.models import AnswerPage
from v1.models import PortalSeeAll, PortalTopic


PROJECT_ROOT = settings.PROJECT_ROOT
FIXTURE_DIR = "{}/ask_cfpb/fixtures/".format(PROJECT_ROOT)
CSV_BASE_DIR = os.getenv('ASK_CSV_BASE_DIR')
SLUGS = {
    'auto_loans': 'Auto loans',
    # 'bank_accounts': 'Bank accounts',
    # 'credit_cards': 'Credit cards',
    # 'credit_reports': 'Credit reports',
    # 'debt_collection': 'Debt collection',
    # 'fraud_and_scams': 'Fraud and scams',
    # 'money_transfers': 'Money transfers',
    # 'mortgages': 'Mortgages',
    # 'payday_loans': 'Payday loans',
    # 'prepaid_cards': 'Prepaid cards',
    # 'reverse_mortgages': 'Reverse mortgages',
    # 'student_loans': 'Student loans',
}


# header = (
#     "ask_id,url,Topic,SubCategories,Audiences,"
#     "PrimaryCategoryTag,CategoryTag2,CategoryTag3,CategoryTag4,"
#     "PrimaryTopicTag,TopicTag2,TopicTag3,TopicTag4,TopicTag5")
def run():
    for slug in SLUGS:
        jfile = "{}{}.json".format(FIXTURE_DIR, slug)
        if os.path.isfile(jfile):
            with open(jfile, 'r') as f:
                output = json.loads(jfile)
        else:
            with open("{}/{}.csv".format(CSV_BASE_DIR, slug), 'r') as f:
                reader = csv.DictReader(f)
                data = [row for row in reader
                        if row['PrimaryTopicTag'] == SLUGS[slug]]
            output = transform_csv(data)
            output_json(output, slug)
            print("Output {}.json".format(slug))
        apply_tags(output)


def apply_tags(data):
    """Apply tagging values to answer pages."""
    migration_user_pk = os.getenv('MIGRATION_USER_PK', 9999)
    user = User.objects.filter(id=migration_user_pk).first()
    for entry in data:
        page = AnswerPage.objects.get(
            language='en', answer_base__pk=entry.get('ask_id'))
        initial_status = page.status_string
        page.get_latest_revision().publish()
        portal_ids = entry.get('portal_ids')
        see_all_ids = entry.get('see_all_ids')
        primary_portal_id = entry.get('primary_portal_id')
        for portal_id in portal_ids:
            topic = PortalTopic.objects.filter(pk=portal_id).first()
            if topic:
                page.portal_topic.add(topic)
        if len(portal_ids) > 1 and primary_portal_id:
            page.primary_portal_topic = PortalTopic.objects.filter(
                pk=primary_portal_id).first()
        for see_id in see_all_ids:
            if see_id in [1, 2, 3, 4]:
                page.portal_see_all.add(PortalSeeAll.objects.get(pk=see_id))
        page.save_revision(user=user).publish()
        print("Portal tags applied to {}".format(page))
        if initial_status == 'draft':
            page.unpublish()


def output_json(data, slug):
    with open("{}/{}.json".format(FIXTURE_DIR, slug), 'w') as f:
        f.write(json.dumps(data, indent=4))


def transform_csv(dict_rows):
    """Turn a CE spreadsheet into a json mapping file."""
    # portal_map = {
    #     'Auto loans': PortalTopic.get(pk=1),
    #     'Bank accounts': PortalTopic.get(pk=2),
    #     'Credit cards': PortalTopic.get(pk=3),
    #     'Credit reports and scores': PortalTopic.get(pk=4),
    #     'Debt collection': PortalTopic.get(pk=5),
    #     'Fraud and scams': PortalTopic.get(pk=7),
    #     'Money transfers': PortalTopic.get(pk=8),
    #     'Mortgages': PortalTopic.get(pk=9),
    #     'Payday loans': PortalTopic.get(pk=10),
    #     'Prepaid cards': PortalTopic.get(pk=11),
    #     'Reverse mortgages': PortalTopic.get(pk=12),
    #     'Student loans': PortalTopic.get(pk=13)
    # }
    portal_ids = {
        'Auto loans': 1,
        'Bank accounts': 2,
        'Credit cards': 3,
        'Credit reports and scores': 4,
        'Debt collection': 5,
        'Fraud and scams': 7,
        'Money transfers': 8,
        'Mortgages': 9,
        'Payday loans': 10,
        'Prepaid cards': 11,
        'Reverse mortgages': 12,
        'Student loans': 13,
    }
    see_all_ids = {
        'Basics': 1,
        'Know your rights': 2,
        'How-to': 3,
        'Key terms': 4,
    }
    output = []
    for row in dict_rows:
        portal = row['PrimaryTopicTag']
        portal_pks = [portal_ids.get(portal)]
        if len(portal_pks) > 1:
            primary_portal = portal_ids.get(row.get('PrimaryTopicTag'))
        else:
            primary_portal = None
        see_alls = [
            tag.strip() for tag in [
                row['PrimaryCategoryTag'],
                row['CategoryTag2'],
                row['CategoryTag3'],
                row['CategoryTag4']]
            if tag.strip()]
        see_all_pks = [see_all_ids.get(tag) for tag in see_alls
                       if see_all_ids.get(tag)]
        entry = {
            'ask_id': row.get('ask_id'),
            'primary_portal_id': primary_portal,
            'portal_ids': portal_pks,
            'see_all_ids': see_all_pks,
        }
        output.append(entry)
    return output
