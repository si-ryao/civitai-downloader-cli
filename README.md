# Civitai Downloader CLI

CLI tool for downloading Civitai models and images with tag-based organization.

## Features

- **Tag-based Organization**: Automatically organizes models by tags (CONCEPT, CHARACTER, STYLE, POSE, etc.)
- **User-based Downloads**: Download all models and images from a specific user
- **Model ID Downloads**: Download specific models by ID
- **Gallery Images**: Download model gallery images with configurable limits
- **User Images**: Download user-posted images with configurable limits
- **SHA256 Verification**: Verify file integrity with SHA256 hashes
- **Rate Limiting**: Respects Civitai API rate limits
- **Resume Support**: Skip already downloaded files

## Installation

```bash
pip install -e .
```

## Usage

### Download all models and images from a user

```bash
# Download all models and user images (default: 50 images)
python -m civitai_dl --user alericiviai --test-mode

# Download all models and up to 100 user images
python -m civitai_dl --user alericiviai --test-mode --max-images 100

# Download to production directory
python -m civitai_dl --user alericiviai --token YOUR_API_KEY
```

### Download a specific model

```bash
python -m civitai_dl --model 123456 --test-mode
```

## Command Line Options

- `--user, -u`: Civitai username to download models from
- `--model, -m`: Specific model ID to download
- `--token, -t`: Civitai API token (or set `CIVITAI_API_KEY` env var)
- `--output, -o`: Output directory (default: `H:\Civitai\civitai-models`)
- `--test-mode`: Run in test mode (save to `./test_downloads/`)
- `--max-images`: Maximum number of user images to download (default: 50)
- `--verbose, -v`: Enable verbose logging

## Folder Structure

Models are organized in the following structure:

```
H:\Civitai\civitai-models\
├── models\
│   ├── {base_model}\           # e.g., "Illustrious", "Pony"
│   │   ├── {tag_category}\     # e.g., "CONCEPT", "CHARACTER", "STYLE"
│   │   │   └── {user}_{model}_{version}\
│   │   │       ├── description.md
│   │   │       ├── {model}.civitai.info
│   │   │       ├── {model}.safetensors
│   │   │       ├── {model}.preview.jpeg
│   │   │       └── Gallery\
│   │   │           ├── {image_id}.jpeg
│   │   │           └── ...
│   │   └── ...
│   └── ...
└── images\
    └── {username}\
        ├── images_metadata.json
        ├── {image_id}.jpeg
        └── ...
```

## Configuration

### API Key

Set your Civitai API key in one of these ways:

1. Environment variable: `export CIVITAI_API_KEY=your_key_here`
2. Command line: `--token your_key_here`
3. Create `api_key.md` file in the project root

### Rate Limiting

The tool automatically respects Civitai API rate limits:
- Model API: 0.5 requests/second
- Image API: 2.0 requests/second

## Development

### Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .[dev]
```

### Code Quality

```bash
# Linting and formatting
ruff check . --fix
python -m black .
python -m mypy .

# Testing
python -m pytest tests/ -v
```

## License

MIT License