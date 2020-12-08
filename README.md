A set of tools and utilities for extracting and shipping raw data to CC.

## Pre-requisites

- python 3.6+ (`python3 --version` to check)
- CC customer ID
- optionally, a data upload key

## Environment setup

- Create a new directory for this tool, with a Python virtual environment (venv), then activate the venv:

  ```
  mkdir coco-agent
  cd coco-agent
  python3 -m venv venv
  source venv/bin/activate
  ```

- Install the latest version of the tool the virtual environment:

  ```
  pip install -U "git+https://github.com/team-machine/coco-agent.git"
  ```

## Extract Git data

To extract metadata from a cloned repo accessible via the file system:

```
coco-agent extract git-repo --customer-id=<customer id> repo-dir
```

where

- `customer id` is an account ID provided by CC
- `repo-dir` is the directory of the Git repository

By default, output is written to the `out` directory.

For additional options, see `./coco-agent extract git-repo --help`

## Upload data

Once desired data has been extracted, it can be securely uploaded to CC from the output directory:

```
coco-agent upload data --customer-id=<customer id> --credentials-file=<credentials file path> out
```

where

- `customer id` is, as before the account ID
- `credentials file path` is the location of the upload credentials JSON file, provided by CC
- `out` is the directory where data was previously extracted

---

## Supported options

Running `coco-agent` will display supported commands and options.

In the same way, description and options for each sub-command can be seen by passing the `--help` argument - e.g. `./coco-agent extract git-repo --help`.
