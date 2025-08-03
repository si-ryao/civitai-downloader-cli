# Base Model Filtering

The Civitai Downloader now supports filtering models by base model type using an opt-in whitelist approach.

## Usage

```bash
# Download all models (default behavior)
python -m civitai_dl --user username --parallel-mode

# Filter to only Illustrious and Pony models
python -m civitai_dl --user username --parallel-mode --base-model-filter model_filter_white_list.txt
```

## Filter File Format

Create a text file with allowed base models, one per line:

```
# Comments start with #
Illustrious
Pony
SD 1.5
SDXL 1.0
```

## Key Features

- **Opt-in filtering**: Only filters when `--base-model-filter` is specified
- **Case-insensitive matching**: "illustrious" matches "Illustrious"
- **Partial matching**: "Pony" matches "Pony Diffusion V6 XL"
- **Filter statistics**: Shows how many models passed/failed the filter
- **Conservative approach**: Models without base model info are skipped when filtering is active

## Example Files

### `model_filter_white_list.txt` - Illustrious + Pony
```
Illustrious
Pony
```

### `model_filter_illustrious_only.txt` - Illustrious Only
```
Illustrious
```

### `model_filter_sdxl_only.txt` - SDXL Family
```
SDXL
```

## Filter Statistics

When filtering is active, you'll see statistics like:
```
🔍 Filter stats: 15/47 models passed filter (32 filtered out)
```

This helps you understand how effective your filter is at reducing downloads.