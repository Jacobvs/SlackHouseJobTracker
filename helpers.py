import json
import typing
import slack_sdk.models

class UserData:
    def __init__(self, user_id: str, user_name: str, enabled: bool, job_name: str, job_days: list):
        self.user_id = user_id
        self.user_name = user_name
        self.enabled = enabled
        self.job_name = job_name
        self.job_days = job_days

    def __init__(self, user_id: str, json_data: dict):
        self.user_id = user_id
        self.user_name = json_data['user_name']
        self.enabled = json_data['enabled']
        self.job_name = json_data['job_name']
        self.job_days = json_data['days']

    def __hash__(self):
        return self.user_id

    def __eq__(self, other):
        return self.user_id == other.user_id


def add_user_blocks(user_name: str, user_id: str, enabled: bool, job_name: str, job_days: str):
    data = json.load(open('base_user_view.json'))
    data['fields'][0]['text'] = f"*{user_name}*"
    data['fields'][1]['text'] = f"*Enabled:\t:white_check_mark:*" if enabled else f"*Enabled:\t:x:*"
    data['accessory']['value'] = user_id

    data['fields'][2]['text'] = f"_Job Name: {job_name}_"
    data['fields'][3]['text'] = f"_Days: {job_days}_" if job_days else f"_Days: N/A_"
    return data


def generate_users_modal(user_data: list):
    data = json.load(open('base_edit_modal.json'))
    user_views = [
        add_user_blocks(user['user_name'], user['user_id'], user['enabled'], user['job_name'], user['job_days'])
        for user in user_data]

    for user_view in reversed(user_views):
        data['blocks'].append(user_view)

    return data


def generate_edit_modal(user: UserData):
    data = json.load(open('user_edit_modal.json'))
    data['title']['text'] = f"Edit {user.user_name}"
    data['blocks'][1]['element']['initial_value'] = user.job_name

    for day in user.job_days:
        data['blocks'][2]['accessory']['initial_options'].append(
            {
                "text": {
                    "type": "plain_text",
                    "text": f"{day}",
                    "emoji": True
                },
                "value": f"{day}"
            }
        )

    data['blocks'][3]['accessory']['initial_options'] = {
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

    data['private_metadata'] = user.user_id

    return data


def get_userdata(client: slack_sdk.WebClient):
    userlist = client.users_list()['members']
    userlist = [u for u in userlist if u['is_bot'] is False and
                ('deleted' not in u or not u['deleted']) and
                u['id'] != 'USLACKBOT']

    all_users = [(user['id'], user['profile']['real_name']) for user in userlist]
    populate_userdata(all_users)

    jobdata = json.load(open('jobdata.json'))

    data = []
    for user in userlist:
        udata = {
            'user_name': user['profile']['real_name'],
            'user_id': user['id'],
            'enabled': jobdata[user['id']]['enabled'],
            'job_name': jobdata[user['id']]['job_name'],
            'job_days': ', '.join(jobdata[user['id']]['days'])
        }
        data.append(udata)

    return data

def get_all_saved_userdata() -> typing.Dict[str, UserData]:
    data = json.load(open('jobdata.json'))
    users = {}
    for uid in data:
        users[uid] = UserData(uid, data[uid])
    return users


def populate_userdata(all_users: typing.List[typing.Tuple[str, str]]):
    data: dict = json.load(open('jobdata.json'))
    for user in all_users:
        key, name = user
        if key not in data:
            data[key] = {
                'user_name': name,
                'enabled': False,
                'job_name': 'N/A',
                'days': []
            }
    json.dump(data, open('jobdata.json', 'w'), indent=4)
    return data

def save_userdata(user_id: str, enabled: bool, job_name: str, job_days: list):
    data = json.load(open('jobdata.json'))
    data[user_id]['enabled'] = enabled
    data[user_id]['job_name'] = job_name
    data[user_id]['days'] = sort_days(job_days)
    json.dump(data, open('jobdata.json', 'w'), indent=4)


def sort_days(days: list):
    days.sort(key=lambda x: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].index(x))
    return days

