📑 Git Commit Report Generator (Azure DevOps)

This tool fetches commits from multiple Azure DevOps repositories, groups them by date → repo → branch, and generates a clean PDF report.

🚀 Installation

Make sure you have Python 3.9+ installed. Then install dependencies:

pip install requests reportlab

⚙️ Configuration

Create a config file (e.g. repos_config.json) like this:

{
  "repositories": [
    {
      "url": "https://dev.azure.com/<REPOSITORY-URL1>",
      "token": "YOUR-PAT1"
    },
    {
      "url": "https://dev.azure.com/<REPOSITORY-URL2>",
      "token": "YOUR-PAT2"
    }
  ]
}


token → Your Azure DevOps Personal Access Token with Code → Read scope.

repos → List of repo URLs to scan. Supports both dev.azure.com and visualstudio.com formats.

▶️ Usage

Run the script like this:

python3 git_rep_gen.py --config repos_config.json --days 30 --output my_commits.pdf --author "YOUR-FULL-NAME"

Options:

--config → Path to your config JSON file.

--days → Limit commits to the last N days (default: 30). Use 0 for all history (may be slow).

--output → PDF file to generate (default: commits_report.pdf).

--start-date 2025-01-01 --end-date 2025-01-31

--author → Filter commits by author’s full name (optional).

📂 Example
python3 git_rep_gen.py \
  --config repos_config.json \
  --days 7 \
  --output weekly_commits.pdf \
  --author "Raunak Srivastava"
