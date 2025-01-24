#!/usr/bin/env python3
import os
import click
import boto3
from dotenv import load_dotenv
import json
import urllib.request
import threading
import sys
from pathlib import Path
import time

# Load environment variables
load_dotenv()

class ProgressPercentage:
    def __init__(self, filename):
        self._filename = filename
        self._size = int(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()
        self._progress_bar = None

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            if not self._progress_bar:
                self._progress_bar = click.progressbar(
                    length=self._size,
                    label=f'Uploading {os.path.basename(self._filename)}'
                )
            
            self._progress_bar.update(bytes_amount)
            if self._seen_so_far >= self._size:
                self._progress_bar.finish()

def init_clients():
    """Initialize AWS clients with credentials from environment variables."""
    region = os.getenv('AWS_REGION')
    if not region:
        raise ValueError("AWS_REGION must be set in .env file")
    
    return (
        boto3.client('s3', region_name=region),
        boto3.client('transcribe', region_name=region)
    )

def download_json_from_url(url):
    """Download and parse JSON from a URL."""
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def write_text_to_file(filepath, text_data):
    """Write text data to a file."""
    with open(filepath, 'w') as f:
        f.write(text_data)

def construct_output_path(output_path):
    """Construct the output file path."""
    if os.path.isdir(output_path):
        return os.path.join(output_path, "transcribed_output.txt")
    return output_path

def get_bucket_name():
    """Get bucket name from environment variables."""
    bucket = os.getenv('AWS_BUCKET_NAME')
    if not bucket:
        raise ValueError("AWS_BUCKET_NAME must be set in .env file")
    return bucket

def construct_object_key(input_file, custom_key=None):
    """Construct S3 object key from input file or custom key."""
    input_path = Path(input_file)
    
    if not custom_key:
        # Use the input filename as the object key
        return input_path.name
    
    # If custom key is provided but doesn't have an extension,
    # use the extension from the input file
    custom_path = Path(custom_key)
    if not custom_path.suffix and input_path.suffix:
        return f"{custom_key}{input_path.suffix}"
    
    return custom_key

def construct_job_name(object_key):
    """Construct a unique job name from the object key."""
    # Remove file extension and replace non-alphanumeric chars with hyphens
    base_name = Path(object_key).stem
    clean_name = ''.join(c if c.isalnum() else '-' for c in base_name)
    # Add timestamp to ensure uniqueness
    return f"{clean_name}-{int(time.time())}"

def start_transcription_job(transcribe_client, bucket, object_key):
    """Start a transcription job for the uploaded file."""
    job_name = construct_job_name(object_key)
    
    # Determine media format from file extension
    media_format = Path(object_key).suffix.lstrip('.').lower()
    if media_format == 'm4a':  # Handle M4A files as MP4
        media_format = 'mp4'
    
    response = transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': f"s3://{bucket}/{object_key}"},
        MediaFormat=media_format,
        LanguageCode='en-US'  # Default to English
    )
    return job_name

def get_default_output_dir():
    """Get default output directory from environment variables or use current directory."""
    output_dir = os.getenv('DEFAULT_OUTPUT_DIR', './transcripts')
    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def wait_for_transcription(transcribe_client, job_name):
    """Wait for transcription job to complete with progress updates."""
    while True:
        response = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        status = response['TranscriptionJob']['TranscriptionJobStatus']
        
        if status == 'COMPLETED':
            return response
        elif status in ['FAILED', 'ERROR']:
            raise Exception(f"Transcription job failed: {response['TranscriptionJob'].get('FailureReason', 'Unknown error')}")
        
        click.echo(f"Current status: {status}... (Press Ctrl+C to stop checking)")
        time.sleep(5)  # Wait 5 seconds before checking again

def save_transcript(transcript_url, output_dir, job_name):
    """Save transcript to a file in the specified directory."""
    json_data = download_json_from_url(transcript_url)
    
    # Extract transcripts
    text_output = ""
    for transcript in json_data['results']['transcripts']:
        text_output += transcript['transcript'] + "\n"

    # Create output filename based on job name (without adding .txt as it will be added by the caller)
    output_file = os.path.join(output_dir, job_name)
    write_text_to_file(output_file, text_output)
    return output_file

@click.group()
def cli():
    """Amazon Transcribe Processing CLI"""
    pass

@cli.command()
@click.option('--input-file', required=True, type=click.Path(exists=True), help='Path to audio file to upload')
@click.option('--key', required=False, help='Optional custom key name for S3 object (will use input filename if not provided)')
@click.option('--wait', is_flag=True, help='Wait for transcription to complete')
def upload(input_file, key, wait):
    """Upload an audio file to S3 and start transcription."""
    try:
        bucket = get_bucket_name()
        object_key = construct_object_key(input_file, key)
        
        s3_client, transcribe_client = init_clients()
        
        # Upload file to S3
        click.echo("Starting upload...")
        s3_client.upload_file(
            input_file, 
            bucket, 
            object_key,
            Callback=ProgressPercentage(input_file)
        )
        click.echo(f"\nSuccessfully uploaded {input_file} to s3://{bucket}/{object_key}")
        
        # Start transcription job
        click.echo("\nStarting transcription job...")
        job_name = start_transcription_job(transcribe_client, bucket, object_key)
        
        if wait:
            click.echo("\nWaiting for transcription to complete...")
            try:
                response = wait_for_transcription(transcribe_client, job_name)
                transcript_url = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                output_file = save_transcript(transcript_url, get_default_output_dir(), job_name)
                click.echo(f"\nTranscription completed! Saved to: {output_file}")
            except KeyboardInterrupt:
                click.echo("\nStopped waiting for completion. You can check the status later with:")
                click.echo(f"python src/cli.py fetch --job-name {job_name}")
        else:
            click.echo(f"Transcription job started with name: {job_name}")
            click.echo(f"Check progress with: python src/cli.py fetch --job-name {job_name}")
        
    except ValueError as ve:
        click.echo(f"\nConfiguration error: {str(ve)}", err=True)
    except Exception as e:
        click.echo(f"\nError: {str(e)}", err=True)

@cli.command()
@click.option('--job-name', required=True, help='Name of the Amazon Transcribe job')
@click.option('--output-file', required=False, type=click.Path(), help='Optional: Custom path for saving text output')
@click.option('--wait', is_flag=True, help='Wait for transcription to complete if still in progress')
def fetch(job_name, output_file, wait):
    """Check transcription status and optionally save results."""
    try:
        _, transcribe_client = init_clients()
        
        if wait:
            click.echo("Waiting for transcription to complete...")
            try:
                response = wait_for_transcription(transcribe_client, job_name)
            except KeyboardInterrupt:
                click.echo("\nStopped waiting. You can check again later.")
                return
        else:
            response = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        
        status = response['TranscriptionJob']['TranscriptionJobStatus']
        click.echo(f"\nJob Status: {status}")
        
        if status == 'COMPLETED':
            transcript_url = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
            
            if output_file:
                # Use custom output path
                output_path = construct_output_path(output_file)
            else:
                # Use default directory and add .txt extension
                output_path = os.path.join(get_default_output_dir(), f"{job_name}.txt")
            
            output_file = save_transcript(transcript_url, os.path.dirname(output_path), os.path.splitext(os.path.basename(output_path))[0])
            click.echo(f"Transcription saved to: {output_file}.txt")
            
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)

if __name__ == '__main__':
    cli() 