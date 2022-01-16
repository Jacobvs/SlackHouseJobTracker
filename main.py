import os
import logging
# Use the package we installed
import typing

import slack_sdk
from slack_bolt import App
import helpers

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
    userdata = helpers.get_userdata(client)
    global user_data
    user_data = helpers.get_all_saved_userdata()
    res = client.views_open(
        trigger_id=body["trigger_id"],
        view=helpers.generate_users_modal(userdata)
    )
    logger.info(res)

@app.view('user_edit_modal_submit')
def user_edit_modal_submit(ack, body, client, logger):
    ack()
    values = body["view"]["state"]["values"]
    logger.info(values)
    uid = body["view"]["private_metadata"]
    enabled = values['jobstatus']['selected']['selected_option']['value'] == 'Active'
    job_name = values['jobname']['plain_text_input-action']['value']
    job_days = [d['value'] for d in values['days']['selected']['selected_options']]
    helpers.save_userdata(uid, enabled, job_name, job_days)
    global user_data
    user_data[uid].enabled = enabled
    user_data[uid].job_name = job_name
    user_data[uid].job_days = job_days

    res = client.views_update(
        view_id=body["view"]["id"],
        view=helpers.generate_users_modal_dict(user_data)
    )


@app.block_action("selected")
def handle_selection(ack, body, client: slack_sdk.WebClient, logger):
    ack()
    logger.info(body)

@app.block_action("edit_user")
def edit_user(ack, body, client: slack_sdk.WebClient, logger):
    ack()
    logger.info(body['actions'])
    logger.info(f"Edit user {body['actions'][0]['value']}")
    logger.info(user_data[body['actions'][0]['value']])
    res = client.views_push(
        trigger_id=body["trigger_id"],
        view=helpers.generate_edit_modal(user_data[body['actions'][0]['value']])
    )
    logger.info(res)

@app.event("app_mention")
def event_test(body, say, logger):
    logger.info(body)
    say("Do your house job already and stop bothering me :clown:")

@app.error
def global_error_handler(error, body, logger):
    logger.exception(error)
    logger.info(body)


@app.use
def log_requests(client, context, logger, payload, next):
    logger.info(payload)
    next()

user_data = helpers.get_all_saved_userdata()
# Start your app
if __name__ == "__main__":

    app.start(int(os.environ.get("PORT")))
