import json
import slack_sdk.models

def add_user_blocks(user_name: str, user_id: str, enabled: bool, job_name: str, job_days: str):
    data = json.load(open('base_user_view.json'))
    data[0]['fields'][0]['text'] = f"*{user_name}*"
    data[0]['fields'][1]['text'] = f"Enabled:\t:white_check_mark:" if enabled else f"Enabled:\t:x:"
    data[0]['accessory']['action_id'] = f"{user_id}_edit_user"
    data[0]['accessory']['value'] = user_id

    data[1]['elements'][0]['text'] = f"Job Name: {job_name}"
    data[1]['elements'][1]['text'] = f"Days: {job_days}"
    return data


def generate_users_modal(user_data: list):
    data = json.load(open('base_edit_modal.json'))
    user_views = [
        add_user_blocks(user['user_name'], user['user_id'], user['enabled'], user['job_name'], user['job_days'])
        for user in user_data]

    for user_view in reversed(user_views):
        data['blocks'].append(user_view[0])
        data['blocks'].append(user_view[1])

    return data


def generate_edit_modal(user_name: str, user_id: str, enabled: bool, job_name: str, job_days: list):
    data = json.load(open('user_edit_modal.json'))
    data['title']['text'] = f"Edit {user_name}"
    data['blocks'][1]['element']['initial_value'] = job_name

    for day in job_days:
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

    data['blocks'][3]['accessory']['initial_option'] = {
            "text": {
                "type": "plain_text",
                "text": "Active",
                "emoji": True
            },
            "value": "Active"
        } if enabled else {
            "text": {
                "type": "plain_text",
                "text": "Inactive",
                "emoji": True
            },
            "value": "Inactive"
        }

    data['private_metadata'] = user_id

    return data


def get_userdata(client: slack_sdk.WebClient):
    userlist = client.users_list()['members']

    all_uids = [user['id'] for user in userlist]
    populate_userdata(all_uids)

    jobdata = json.load(open('jobdata.json'))

    data = []
    for user in userlist:
        udata = {
            'user_name': user['profile']['real_name'],
            'user_id': user['id'],
            'enabled': jobdata[user['id']]['enabled'],
            'job_name': jobdata[user['id']]['job_name'],
            'job_days': jobdata[user['id']]['days'].join(', ')
        }
        data.append(udata)

    return data


def populate_userdata(all_uids: list):
    data: dict = json.load(open('jobdata.json'))
    for key in all_uids:
        if key not in data:
            data[key] = {
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


