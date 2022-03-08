A set of tools and utilities for extracting and shipping raw data to ConnectedCompany ("CC").

## Pre-requisites

- python 3.6+ (`python3 --version` to check)
- CC connector ID - this is a string provided by CC, strucured like `customer-id>/<source-type>/<source-id>`
- optionally, a credentials file, to push data extracts and / or logs to CC

## Installation

- Create a new directory for this tool, with a Python virtual environment (venv), then activate the venv:

  ```
  mkdir coco-agent
  cd coco-agent
  python3 -m venv venv
  source venv/bin/activate
  ```

- Install the latest version of the tool the virtual environment:

  ```
  pip install -U coco-agent
  ```

## Extract metadata from a Git repository

To extract metadata from a cloned repo accessible via the file system:

```
coco-agent extract git-repo --connector-id=<connector id> repo-dir
```

where

- `connector id` is the connector ID mentioned above, provided by CC
- `repo-dir` is the directory of the Git repository

By default, output is written to the `out` directory.

For additional options, including specifying date ranges, see `./coco-agent extract git-repo --help`

#### Additional data sources

Each will have its own connector-id. Simply re-run the `extract` command, pointing at each additional source as desired.

## Upload data

Once desired data has been extracted, it can be securely uploaded to CC from the output directory:

```
coco-agent upload data --credentials-file=<credentials file path> <connector id> <directory>
```

where

- `credentials file path` is the location of the upload credentials JSON file, provided by CC
- `connector id` is, as before, the connector ID for the data source
- `directory` is the directory where data was previously extracted (`./out` by default)

---

## Supported options

Invoking `coco-agent` without arguments will display supported commands and options.

`coco-agent version` will display the current version.

In the same way, description and options for each sub-command can be seen by passing the `--help` argument - e.g. `coco-agent extract git-repo --help`.
