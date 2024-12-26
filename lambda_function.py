import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses_client = boto3.client('ses')
client = boto3.client('workmail')

def send_confirmation_email(ClientEmail):
    try:
        # Ensure we encode all text to bytes before concatenating
        raw_message = (
            'From: noreply@****.****\n'
            f'To: {ClientEmail}\n'
            'Subject: Your Active Directory and Mailing Accounts Are Ready\n'
            'MIME-Version: 1.0\n'
            'Content-Type: text/html; charset=UTF-8\n\n'
            '''
            <html>
            <head>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        color: #333;
                        line-height: 1.6;
                        margin: 0;
                        padding: 0;
                        background-color: #f4f7fa;
                    }
                    .email-container {
                        width: 100%;
                        max-width: 600px;
                        margin: 0 auto;
                        background-color: #ffffff;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }
                    .header {
                        text-align: center;
                        margin-bottom: 20px;
                    }
                    .header h1 {
                        font-size: 24px;
                        color: #333;
                        margin: 0;
                    }
                    .content {
                        margin-bottom: 20px;
                    }
                    .content p {
                        font-size: 16px;
                        color: #555;
                        margin: 10px 0;
                    }
                    .cta {
                        display: block;
                        width: 100%;
                        padding: 12px 20px;
                        background-color: #cbc3e3;  /* Purple color */
                        color: white;
                        text-align: center;
                        text-decoration: none;
                        font-size: 18px;
                        border-radius: 4px;
                        margin-top: 20px;
                    }
                    .cta:hover {
                        background-color: #5a2a8b;  /* Darker purple */
                    }
                    .footer {
                        text-align: center;
                        margin-top: 20px;
                        font-size: 14px;
                        color: #888;
                    }
                    .footer a {
                        color: #cbc3e3;  /* Purple color for the email */
                        text-decoration: none;
                    }
                    .footer a:hover {
                        text-decoration: underline;
                    }
                </style>
            </head>
            <body>
                <div class="email-container">
                    <div class="header">
                        <h1>Welcome to Your New Account</h1>
                    </div>
                    <div class="content">
                        <p>Dear user,</p>
                        <p>We are pleased to inform you that your Active Directory and mailing accounts are now ready for use.</p>
                        <p>You can access your email account by clicking the link below:</p>
                        <a href="https://******.awsapps.com/mail" class="cta">Access Your Email</a>
                        <p>Thank you for your attention, and we look forward to having you!</p>
                    </div>
                    <div class="footer">
                        <p>Best regards,</p>
                        <p>The Boubekeur Team</p>
                        <p>If you have any questions, feel free to reach out to us at <a href="mailto:help@****.****">help@****.****</a>.</p>
                    </div>
                </div>
            </body>
            </html>
            '''
        ).encode('utf-8')  # Ensure the message is encoded as bytes

        response = ses_client.send_raw_email(
            Source='noreply@****.****',  # Replace with your sender email address
            Destinations=[ClientEmail],  # The recipient's email address
            RawMessage={'Data': raw_message},  # Send the raw email data
            FromArn='*****',  # Replace with the ARN of your sender email identity (SES)
            SourceArn='*****',  # Replace with the ARN of your source email identity (SES)
            ReturnPathArn='',  # Replace with the ARN for your return path email identity (SES)
            Tags=[{
                'Name': 'string',  
                'Value': 'string' 
            }],
        )
        logger.info(f"Email sent successfully to {ClientEmail}")
        return response
    except ClientError as e:
        logger.error(f"Error sending email to {ClientEmail}: {e}")
        return None


def lambda_handler(event, context):
    organization_id = 'm-*****************'
    FirstName = event.get('FirstName')
    LastName = event.get('LastName')
    Password = event.get('Password')
    displayname = f'{FirstName} {LastName}'
    name = f'{FirstName}.{LastName}'
    mail = f'{FirstName}.{LastName}@****.****'
    group_ids = event.get('groupIds')
    client_email = event.get('ClientEmail')  # Getting the client email for sending confirmation

    if not all([FirstName, LastName, Password, client_email]):
        logger.error("Missing required user details: FirstName, LastName, Password, or ClientEmail")
        return {
            'statusCode': 400,
            'body': "Missing required fields: FirstName, LastName, Password, and/or ClientEmail"
        }

    try:
        logger.info("Attempting to create user")
        response = client.create_user(
            OrganizationId=organization_id,
            Name=name,
            DisplayName=displayname,
            Password=Password,
            Role='USER',
            FirstName=FirstName,
            LastName=LastName,
            HiddenFromGlobalAddressList=False
        )
        user_id = response['UserId']
        logger.info(f"User created successfully: {user_id}")
        
        # Register user to WorkMail
        try:
            logger.info("Registering user to WorkMail")
            register_response = client.register_to_work_mail(
                OrganizationId=organization_id,
                EntityId=user_id,
                Email=mail
            )

            # Ensure email is enabled
            registered_status = register_response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            if registered_status == 200:
                logger.info("User registered to WorkMail and email enabled successfully")
            else:
                logger.error("Failed to enable email for the user")
                return {
                    'statusCode': 500,
                    'body': f"Failed to enable email for the user: HTTPStatusCode {registered_status}"
                }

        except ClientError as e:
            logger.error(f"ClientError during WorkMail registration: {e}")
            return {
                'statusCode': 500,
                'body': f"Error during WorkMail registration: {str(e)}"
            }

        # Associate user with groups
        if group_ids:
            try:
                logger.info(f"Attempting to associate user {user_id} with groups: {group_ids}")
                results = []

                for group_id in group_ids:
                    try:
                        logger.info(f"Attempting to associate user {user_id} with group {group_id}")
                        response = client.associate_member_to_group(
                            OrganizationId=organization_id,
                            GroupId=group_id,
                            MemberId=user_id
                        )
                        logger.info(f"Successfully associated user {user_id} with group {group_id}")
                        results.append({
                            'groupId': group_id,
                            'status': 'success',
                            'response': response
                        })
                    except ClientError as e:
                        logger.error(f"ClientError for group {group_id}: {e}")
                        results.append({
                            'groupId': group_id,
                            'status': 'failure',
                            'error': str(e)
                        })
                    except Exception as e:
                        logger.error(f"Unexpected error for group {group_id}: {e}")
                        results.append({
                            'groupId': group_id,
                            'status': 'failure',
                            'error': str(e)
                        })

                # Send confirmation email to the client
                send_confirmation_email(client_email)

                return {
                    'statusCode': 200,
                    'body': {
                        'message': f"User created and registered successfully: {user_id}",
                        'groupResults': results
                    }
                }

            except ClientError as e:
                logger.error(f"Error associating user with groups: {e}")
                return {
                    'statusCode': 500,
                    'body': f"Error associating user with groups: {str(e)}"
                }

        # No groups to associate
        send_confirmation_email(client_email)

        return {
            'statusCode': 200,
            'body': f"User created and registered successfully: {user_id}, but no groups were provided to associate."
        }

    except ClientError as e:
        logger.error(f"ClientError during user creation: {e}")
        return {
            'statusCode': 500,
            'body': f"Error during user creation: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': f"Unexpected error: {str(e)}"
        }
# Usage: 

#{
 # "FirstName": "johtfftun",
  #"LastName": "doe",
  #"ClientEmail": "email@email.email",
  #"Password": "StrongPassword123",
  #"groupIds": [
   # "Group1",
   # "Group2",
   # "Group3"
  #]
#}



# here is the documentation used: 
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ses.html
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/workmail.html
