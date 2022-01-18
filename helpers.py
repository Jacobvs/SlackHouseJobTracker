import json
import typing

import pymongo
import slack_sdk.models

class UserData:
    def __init__(self, user_id: str, user_name: str, enabled: bool, job_name: str, job_days: list, job_tasks: list):
        self.user_id = user_id
        self.user_name = user_name
        self.enabled = enabled
        self.job_name = job_name
        self.job_days = job_days
        self.job_tasks = job_tasks

    def __init__(self, json_data: dict):
        self.user_id = json_data['user_id']
        self.user_name = json_data['user_name']
        self.enabled = json_data['enabled']
        self.job_name = json_data['job_name']
        self.job_days = json_data['days']
        self.job_tasks = json_data['tasks']

    def __hash__(self):
        return self.user_id

    def __eq__(self, other):
        return self.user_id == other.user_id

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'user_name': self.user_name,
            'enabled': self.enabled,
            'job_name': self.job_name,
            'days': self.job_days,
            'tasks': self.job_tasks
        }


def add_user_blocks(user_name: str, user_id: str, enabled: bool, job_name: str, job_days: str):
    data = json.load(open('base_user_view.json'))
    data['fields'][0]['text'] = f"*{user_name}*"
    data['fields'][1]['text'] = f"*Enabled:\t:white_check_mark:*" if enabled else f"*Enabled:\t:x:*"
    data['accessory']['value'] = user_id

    data['fields'][2]['text'] = f"_Job Name: {job_name}_" if job_name else "_Job Name: N/A_"
    data['fields'][3]['text'] = f"_Days: {job_days}_" if job_days else f"_Days: N/A_"
    return data


def generate_users_modal(user_data: typing.Union[list, typing.Dict[str, UserData]], ref_channel_id: str):
    data = json.load(open('base_edit_modal.json'))
    if isinstance(user_data, dict):
        user_views = [
            add_user_blocks(user.user_name, user.user_id, user.enabled, user.job_name, ", ".join(user.job_days))
            for user in sorted(user_data.values(), key=lambda x: x.user_name.upper(), reverse=True)]
    else:
        user_views = [
            add_user_blocks(user['user_name'], user['user_id'], user['enabled'], user['job_name'], user['job_days'])
            for user in sorted(user_data, key=lambda x: x['user_name'].upper(), reverse=True)]

    for user_view in reversed(user_views):
        data['blocks'].append(user_view)

    data['private_metadata'] = ref_channel_id

    return data


def generate_edit_modal(user: UserData):
    data = json.load(open('user_edit_modal.json'))
    data['title']['text'] = f"Edit {user.user_name}"
    data['blocks'][1]['element']['initial_value'] = user.job_name

    if user.job_days:
        days = []
        for day in user.job_days:
            days.append(
                {
                    "text": {
                        "type": "plain_text",
                        "text": f"{day}",
                        "emoji": True
                    },
                    "value": f"{day}"
                }
            )
        data['blocks'][2]['accessory']['initial_options'] = days

    data['blocks'][3]['accessory']['initial_option'] = {
            "text": {
                "type": "plain_text",
                "text": "Active",
                "emoji": True
            },
            "value": "Active"
        } if user.enabled else {
            "text": {
                "type": "plain_text",
                "text": "Inactive",
                "emoji": True
            },
            "value": "Inactive"
        }

    if user.job_tasks:
        data['blocks'][4]['initial_value'] = "\n".join(user.job_tasks)

    data['private_metadata'] = user.user_id

    return data


def get_slack_userdata(user_db: pymongo.collection, client: slack_sdk.WebClient):
    userlist = client.users_list()['members']
    userlist = [u for u in userlist if u['is_bot'] is False and
                ('deleted' not in u or not u['deleted']) and
                u['id'] != 'USLACKBOT']

    all_users = [(user['id'], user['profile']['real_name']) for user in userlist]
    populate_userdata(user_db, all_users)

    data = []
    for user in userlist:
        jobdata = user_db.find_one({'user_id': user['id']})
        udata = {
            'user_name': user['profile']['real_name'],
            'user_id': user['id'],
            'enabled': jobdata['enabled'],
            'job_name': jobdata['job_name'],
            'job_days': ', '.join(jobdata['days']),
            'tasks': jobdata['tasks']
        }
        data.append(udata)

    return data

def get_all_saved_userdata(user_db: pymongo.collection) -> typing.Dict[str, UserData]:
    users = {}
    for user in user_db.find():
        users[user['user_id']] = UserData(user)

    return users

def get_closed_message(user_cache: typing.Dict[str, UserData]) -> dict:
    enabled_users = sorted([user for user in user_cache.values() if user.enabled], key=lambda x: x.user_name.upper())
    data = json.load(open('closed_settings_message.json'))
    data[3]['text']['text'] = f"Users Enabled:\t{len(enabled_users)}/{len(user_cache)}"

    section = {"type": "section", "fields": []}
    for i, user in enumerate(enabled_users):
        section['fields'].append({
            "type": "mrkdwn",
            "text": f"<@{user.user_id}> {user.job_name} - {', '.join(user.job_days) if user.job_days else 'N/A'}"
        })
        if i % 10 == 0:
            data.append(section)
            section = {"type": "section", "fields": []}

    return data


def populate_userdata(user_db: pymongo.collection, all_users: typing.List[typing.Tuple[str, str]]):
    for user in all_users:
        key, name = user
        if not user_db.find_one({'user_id': key}):
            user_db.insert_one({
                'user_id': key,
                'user_name': name,
                'enabled': False,
                'job_name': '',
                'days': [],
                'tasks': []
            })


def save_userdata(user_db: pymongo.collection, user_id: str, enabled: bool, job_name: str, job_days: list, tasks: list):
    user_db.find_one_and_update({'user_id': user_id}, {'$set': {
        'enabled': enabled,
        'job_name': job_name,
        'days': sort_days(job_days),
        'tasks': tasks
    }})

def sort_days(days: list):
    days.sort(key=lambda x: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].index(x))
    return days

def users_by_days(user_db: pymongo.collection, days: list) -> typing.Dict[str, UserData]:
    daily_users = {}
    for user in user_db.find():
        if user['enabled'] and user['days']:
            for day in user['days']:
                if day not in daily_users:
                    daily_users[day] = []
                daily_users[day].append(user['user_id'])
