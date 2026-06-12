import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import requests
from twilio.rest import Client
import threading
from datetime import datetime
from pathlib import Path
import json

class AlertSystem:
    """Alert system for defect detection notifications"""
    
    def __init__(self, config_path='alert_config.json'):
        self.config = self.load_config(config_path)
        self.alert_history = []
        self.alert_callbacks = []
        
    def load_config(self, config_path):
        default_config = {
            'email': {
                'enabled': True,
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': 'your-email@gmail.com',
                'password': 'your-app-password',
                'from_email': 'defect-alert@company.com',
                'to_emails': ['operator@company.com', 'supervisor@company.com']
            },
            'sms': {
                'enabled': False,
                'account_sid': 'your-twilio-account-sid',
                'auth_token': 'your-twilio-auth-token',
                'from_number': '+1234567890',
                'to_numbers': ['+0987654321']
            },
            'slack': {
                'enabled': False,
                'webhook_url': 'https://hooks.slack.com/services/...',
                'channel': '#defect-alerts'
            },
            'thresholds': {
                'critical_defect_count': 5,
                'defect_rate_threshold': 10.0,
                'consecutive_defects': 3,
                'severity_levels': ['Critical']
            }
        }
        config_path = Path(config_path)
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def register_callback(self, callback):
        self.alert_callbacks.append(callback)
    
    def send_alert(self, detection_result, alert_type='defect_detected'):
        severity_raw = detection_result.get('severity', 'Unknown')
        if isinstance(severity_raw, dict):
            severity = severity_raw.get('level', 'Unknown')
        else:
            severity = severity_raw
            
        if severity not in self.config['thresholds']['severity_levels']:
            return
        alert_message = self._create_alert_message(detection_result, alert_type)
        threads = []
        if self.config['email']['enabled']:
            thread = threading.Thread(target=self._send_email_alert, args=(alert_message,))
            threads.append(thread)
        if self.config['sms']['enabled']:
            thread = threading.Thread(target=self._send_sms_alert, args=(alert_message,))
            threads.append(thread)
        if self.config['slack']['enabled']:
            thread = threading.Thread(target=self._send_slack_alert, args=(alert_message,))
            threads.append(thread)
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.alert_history.append({
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'severity': severity,
            'message': alert_message
        })
        for callback in self.alert_callbacks:
            callback(alert_message)
            
    def _create_alert_message(self, detection_result, alert_type):
        severity_raw = detection_result.get('severity', {})
        if isinstance(severity_raw, dict):
            severity_level = severity_raw.get('level', 'Unknown')
            severity_score = severity_raw.get('score', 0.0)
        else:
            severity_level = severity_raw
            severity_score = 0.0
            
        defects = detection_result.get('defects', [])
        message = {
            'subject': f'🚨 {severity_level} Defect Alert - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'body': f"""
Defect Detection Alert
======================
Alert Type: {alert_type}
Severity: {severity_level}
Severity Score: {severity_score:.2f}
Number of Defects: {len(defects)}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Detected Defects:
""",
            'html_body': f"""
<html>
<head><style>
    .critical {{ color: red; font-weight: bold; }}
    .major {{ color: orange; font-weight: bold; }}
    .minor {{ color: yellow; }}
</style></head>
<body>
    <h2>Defect Detection Alert</h2>
    <table border="1" cellpadding="5">
        <tr><td><strong>Alert Type</strong></td><td>{alert_type}</td></tr>
        <tr class="{str(severity_level).lower()}">
            <td><strong>Severity</strong></td><td>{severity_level}</td>
        </tr>
        <tr><td><strong>Score</strong></td><td>{severity_score:.2f}</td></tr>
        <tr><td><strong>Number of Defects</strong></td><td>{len(defects)}</td></tr>
        <tr><td><strong>Timestamp</strong></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
    </table>
    <h3>Detected Defects:</h3>
    <ul>
"""
        }
        for i, defect in enumerate(defects[:10]):
            message['body'] += f"\n{i+1}. {defect.get('class', 'Unknown')} - Confidence: {defect.get('confidence', 0):.2%}"
            message['html_body'] += f"<li>{defect.get('class', 'Unknown')} - Confidence: {defect.get('confidence', 0):.2%}</li>"
        message['html_body'] += "</ul></body></html>"
        return message
    
    def _send_email_alert(self, message):
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = message['subject']
            msg['From'] = self.config['email']['from_email']
            msg['To'] = ', '.join(self.config['email']['to_emails'])
            msg.attach(MIMEText(message['body'], 'plain'))
            msg.attach(MIMEText(message['html_body'], 'html'))
            server = smtplib.SMTP(
                self.config['email']['smtp_server'],
                self.config['email']['smtp_port']
            )
            server.starttls()
            server.login(
                self.config['email']['username'],
                self.config['email']['password']
            )
            server.send_message(msg)
            server.quit()
            print(f"Email alert sent to {', '.join(self.config['email']['to_emails'])}")
        except Exception as e:
            print(f"Failed to send email alert: {e}")
    
    def _send_sms_alert(self, message):
        try:
            client = Client(
                self.config['sms']['account_sid'],
                self.config['sms']['auth_token']
            )
            sms_body = f"{message['subject']}\n{message['body'][:500]}"
            for number in self.config['sms']['to_numbers']:
                message_obj = client.messages.create(
                    body=sms_body,
                    from_=self.config['sms']['from_number'],
                    to=number
                )
                print(f"SMS sent to {number}: {message_obj.sid}")
        except Exception as e:
            print(f"Failed to send SMS alert: {e}")
    
    def _send_slack_alert(self, message):
        try:
            webhook_url = self.config['slack']['webhook_url']
            payload = {
                'channel': self.config['slack']['channel'],
                'username': 'Defect Detection Bot',
                'text': message['body'],
                'icon_emoji': ':warning:',
                'attachments': [{
                    'color': 'danger',
                    'title': message['subject'],
                    'fields': [
                        {
                            'title': 'Severity',
                            'value': message.get('severity', 'Unknown'),
                            'short': True
                        }
                    ]
                }]
            }
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 200:
                print("Slack alert sent successfully")
            else:
                print(f"Failed to send Slack alert: {response.status_code}")
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")
