import os
import json
import boto3
from urllib.request import urlopen

class TranscribeManager:
    def __init__(self):
        self.s3_client = boto3.client('s3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        self.transcribe_client = boto3.client('transcribe',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        self.bucket_name = os.getenv('AWS_BUCKET_NAME', 'transcribe-audio-files')

    def upload_file(self, file_path):
        """Upload a file to S3"""
        file_name = os.path.basename(file_path)
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, file_name)
            return f"s3://{self.bucket_name}/{file_name}"
        except Exception as e:
            raise Exception(f"Failed to upload file: {str(e)}")

    def start_transcription_job(self, job_name, file_uri):
        """Start an AWS Transcribe job"""
        try:
            self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': file_uri},
                MediaFormat=file_uri.split('.')[-1].lower(),
                LanguageCode='en-US'
            )
        except Exception as e:
            raise Exception(f"Failed to start transcription job: {str(e)}")

    def get_transcription_status(self, job_name):
        """Get the status of a transcription job"""
        try:
            response = self.transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            return response['TranscriptionJob']['TranscriptionJobStatus']
        except Exception as e:
            raise Exception(f"Failed to get transcription status: {str(e)}")

    def get_transcript(self, job_name):
        """Get the transcript from a completed job"""
        try:
            response = self.transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            if response['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
                transcript_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                with urlopen(transcript_uri) as response:
                    data = json.loads(response.read())
                    return data['results']['transcripts'][0]['transcript']
            return None
        except Exception as e:
            raise Exception(f"Failed to get transcript: {str(e)}") 