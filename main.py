import os
import logging
# Use the package we installed
import typing

import slack_sdk
from slack_bolt import App
import helpers
import pymongo

mongo_client = pymongo.MongoClient(
    f"mongodb+srv://{os.environ.get('MONGO_USERNAME')}:{os.environ.get('MONGO_PW')}"
    f"@cluster0.9esex.mongodb.net/SlackHouseJobs?retryWrites=true&w=majority")
user_db = mongo_client.SlackHouseJobs.userdata

user_cache = helpers.get_all_saved_userdata(user_db)

logging.basicConfig(level=int(os.environ.get("LOGLEVEL")))

# Set house manager uid (In slack: view full profile -> more -> copy member id)
HOUSE_MANAGER_UID = os.environ.get("HOUSE_MANAGER_UID")
DEVELOPER_UID = os.environ.get("DEVELOPER_UID")

# Initializes your app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@app.command('/configurejobs')
def configure_jobs(body, client, ack, logger):
    user_id = body["user_id"]
    if user_id not in [HOUSE_MANAGER_UID, DEVELOPER_UID]:
        return ack("You are not authorized to configure jobs.")
    ack(f"Hi <@{user_id}>!\nYou can configure house jobs in the popup panel.")
    # Send interactive message to the user
    # TODO: refresh user list with any missing users
    # TODO: Buttons - previous, next, done, cancel
    res = client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": "Edit Users"
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel"
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "Loading... Please wait."
                    }
                }
            ]
        })
    global user_cache
    user_cache = helpers.get_slack_userdata(user_cache, user_db, client)
    view = helpers.generate_users_modal(user_cache, body['channel_id'])
    res = client.views_update(
        view_id=res["view"]["id"],
        view=view
    )
    logger.info(res)

@app.view('user_edit_modal_submit')
def user_edit_modal_submit(ack, body, client: slack_sdk.WebClient, logger):
    values = body["view"]["state"]["values"]
    logger.info(values)

    # Validate user task input
    tasks: str = values['tasks']['plain_text_input-action']['value']
    if not tasks:
        res = ack(options={
              "response_action": "errors",
              "errors": {
                "tasks": "Please enter at least one task, with a new line between each task."
              }
        })
    else: ack()

    tasks: list = tasks.split("\n")
    uid = body["view"]["private_metadata"].split(",")[0]
    enabled = values['jobstatus']['selected']['selected_option']['value'] == 'Active'
    job_name = values['jobname']['plain_text_input-action']['value']
    job_days = [d['value'] for d in values['days']['selected']['selected_options']]
    helpers.save_userdata(user_db, uid, enabled, job_name, job_days, tasks)
    global user_cache
    user_cache[uid].enabled = enabled
    user_cache[uid].job_name = job_name
    user_cache[uid].job_days = job_days
    user_cache[uid].job_tasks = tasks
    try:
        res = client.views_update(
            view_id=body["view"]["root_view_id"],
            view=helpers.generate_users_modal(user_cache,
                ref_channel_id=body["view"]["private_metadata"].split(",")[1])
                if ',' in body["view"]["private_metadata"] else
                body["view"]["private_metadata"]
        )
    except slack_sdk.errors.SlackApiError:
        pass

@app.view({'type': 'view_closed', 'callback_id': 'userlist', 'view': {'type': 'modal'}})
def userlist(ack, body, client: slack_sdk.WebClient, logger):
    ack()
    client.chat_postMessage(channel=body["view"]["private_metadata"],
                            blocks=helpers.get_closed_message(user_cache))
    logger.info(body)


@app.block_action("selected")
def handle_selection(ack, body, client: slack_sdk.WebClient, logger):
    ack()
    logger.info(body)


@app.block_action("edit_user")
def edit_user(ack, body, client: slack_sdk.WebClient, logger):
    ack()
    logger.info(body['actions'])
    logger.info(f"Edit user {body['actions'][0]['value']}")
    logger.info(user_cache[body['actions'][0]['value']])
    view = helpers.generate_edit_modal(user_cache[body['actions'][0]['value']])
    view["private_metadata"] += "," + body['view']['private_metadata']
    res = client.views_push(
        trigger_id=body["trigger_id"],
        view=view
    )
    logger.info(res)


@app.event("app_mention")
def event_test(body, say, logger):
    logger.info(body)
    say(text="Do your house job already and stop bothering me :clown:", channel=body["event"]["channel"])


@app.error
def global_error_handler(error, body, logger):
    logger.exception(error)
    logger.info(body)


@app.use
def log_requests(client, context, logger, payload, next):
    logger.info(payload)
    next()

# Start your app
if __name__ == "__main__":
    app.start(int(os.environ.get("PORT")))
