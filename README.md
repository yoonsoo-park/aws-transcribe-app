# AWS Transcribe App

A Python command-line application for transcribing audio files using AWS Transcribe service.

## Prerequisites

- Python 3.9+
- AWS Account with access to S3 and Transcribe services
- AWS credentials (access key and secret key)

## Setup

1. Create a virtual environment and activate it:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with your AWS credentials:

```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=your_region
AWS_BUCKET_NAME=your_bucket_name
DEFAULT_OUTPUT_DIR=./transcripts  # Optional: defaults to ./transcripts if not set
```

## Usage

The application provides two main commands: `upload` and `fetch`.

### Upload an audio file

Upload a file to S3 and start transcription:

```bash
python src/cli.py upload --input-file PATH_TO_AUDIO_FILE [--key CUSTOM_NAME] [--wait]
```

Options:

- `--input-file`: Path to the audio file (required)
- `--key`: Optional custom name for the S3 object (will use input filename if not provided)
- `--wait`: Optional flag to wait for transcription to complete and save results

Examples:

```bash
# Basic upload with automatic naming
python src/cli.py upload --input-file ./recording.m4a

# Upload with custom name (extension will be added automatically)
python src/cli.py upload --input-file ./recording.m4a --key meeting-jan-23

# Upload and wait for transcription to complete
python src/cli.py upload --input-file ./recording.m4a --wait
```

### Check transcription status and fetch results

Check the status of a transcription job and optionally save the transcript:

```bash
python src/cli.py fetch --job-name JOB_NAME [--output-file PATH] [--wait]
```

Options:

- `--job-name`: Name of the transcription job (required)
- `--output-file`: Optional custom path for saving the transcript
- `--wait`: Optional flag to wait for completion if the job is still in progress

Examples:

```bash
# Check status
python src/cli.py fetch --job-name meeting-jan-23-1234567890

# Check status and wait for completion
python src/cli.py fetch --job-name meeting-jan-23-1234567890 --wait

# Save to custom location
python src/cli.py fetch --job-name meeting-jan-23-1234567890 --output-file ./my-transcripts/meeting.txt
```

## Supported Audio Formats

- MP3
- WAV
- FLAC
- OGG
- M4A (automatically handled as MP4)

## Output Files

- By default, transcripts are saved in the directory specified by `DEFAULT_OUTPUT_DIR` in your `.env` file
- If `DEFAULT_OUTPUT_DIR` is not set, transcripts are saved in a `./transcripts` directory
- Files are named using the job name: `{job_name}.txt`
- You can specify a custom output location using the `--output-file` option with the fetch command

## Notes

- The application requires an active internet connection
- Large audio files may take longer to process
- Make sure your AWS credentials have the necessary permissions for S3 and Transcribe services
- Progress tracking:
  - Upload progress is shown with a progress bar
  - Transcription progress can be monitored in real-time using the `--wait` flag
  - You can interrupt progress monitoring anytime with Ctrl+C
- The S3 bucket is configured through the `AWS_BUCKET_NAME` environment variable
- File extensions are handled automatically:
  - When using a custom key without an extension, the original file's extension is added
  - M4A files are automatically processed as MP4 format for AWS Transcribe
