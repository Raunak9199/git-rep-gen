#!/usr/bin/env python3
"""
Azure DevOps Commits PDF Generator
Fetches commits from multiple Azure DevOps repositories and generates a PDF report
organized by date, branches, and repositories.
"""

import requests
import json
from datetime import datetime, timedelta
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import black, blue, gray, lightgrey
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import argparse
from collections import defaultdict
import sys

class AzureDevOpsCommitsFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.commits_data = []
    
    def setup_auth(self, token):
        """Setup authentication for Azure DevOps API"""
        # Azure DevOps uses PAT (Personal Access Token) in Basic Auth format
        auth_string = f":{token}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json'
        })
    
    def parse_repo_url(self, repo_url):
        """Parse Azure DevOps repository URL to extract organization, project, and repo name"""
        # Expected format: https://dev.azure.com/{organization}/{project}/_git/{repository}
        # or: https://{organization}.visualstudio.com/{project}/_git/{repository}
        
        if 'dev.azure.com' in repo_url:
            parts = repo_url.replace('https://dev.azure.com/', '').split('/')
            organization = parts[0]
            project = parts[1]
            repo_name = parts[3] if len(parts) > 3 else parts[2].replace('_git/', '')
        elif 'visualstudio.com' in repo_url:
            parts = repo_url.replace('https://', '').split('/')
            organization = parts[0].replace('.visualstudio.com', '')
            project = parts[1]
            repo_name = parts[3] if len(parts) > 3 else parts[2].replace('_git/', '')
        else:
            raise ValueError(f"Unsupported repository URL format: {repo_url}")
        
        return organization, project, repo_name
    
    def fetch_commits(self, repo_url, token, days_back=30, skip_branches=False, author_filter=None):
        """Fetch commits from a repository"""
        try:
            self.setup_auth(token)
            organization, project, repo_name = self.parse_repo_url(repo_url)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Azure DevOps REST API endpoint for commits
            api_url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo_name}/commits"
            
            params = {
                'searchCriteria.fromDate': start_date.isoformat(),
                'searchCriteria.toDate': end_date.isoformat(),
                'api-version': '7.0',
                '$top': 1000  # Maximum commits to fetch
            }
            
            # Add author filter if provided
            if author_filter:
                params['searchCriteria.author'] = author_filter
            
            print(f"Fetching commits from {repo_name}...")
            response = self.session.get(api_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            commits = data.get('value', [])
            
            # Additional client-side filtering if author_filter is provided
            if author_filter:
                filtered_commits = []
                for commit in commits:
                    author_email = commit.get('author', {}).get('email', '').lower()
                    author_name = commit.get('author', {}).get('name', '').lower()
                    author_filter_lower = author_filter.lower()
                    
                    # Match by email or name
                    if (author_filter_lower in author_email or 
                        author_filter_lower in author_name or
                        author_email == author_filter_lower or
                        author_name == author_filter_lower):
                        filtered_commits.append(commit)
                commits = filtered_commits
            
            # Get branches for each commit
            for commit in commits:
                commit['repository'] = repo_name
                commit['organization'] = organization
                commit['project'] = project
                # Fetch branch information for each commit
                if skip_branches:
                    commit['branches'] = ['main']  # Default branch when skipping detection
                else:
                    commit['branches'] = self.get_commit_branches(organization, project, repo_name, commit['commitId'])
            
            print(f"Found {len(commits)} commits in {repo_name}")
            return commits
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching commits from {repo_url}: {e}")
            return []
        except Exception as e:
            print(f"Error processing repository {repo_url}: {e}")
            return []
    
    def get_commit_branches(self, organization, project, repo_name, commit_id):
        """Get branches that contain a specific commit"""
        try:
            # Method 1: Get all branches and check which ones contain this commit
            api_url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo_name}/refs"
            params = {
                'api-version': '7.0',
                'filter': 'heads/'
            }
            
            response = self.session.get(api_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                branches_found = []
                
                # Get up to 5 most common branches to check
                common_branches = ['main', 'master', 'develop', 'dev', 'feature']
                all_branches = []
                
                for ref in data.get('value', []):
                    if ref['name'].startswith('refs/heads/'):
                        branch_name = ref['name'].replace('refs/heads/', '')
                        all_branches.append(branch_name)
                
                # Check common branches first, then others
                branches_to_check = []
                for branch in common_branches:
                    if branch in all_branches:
                        branches_to_check.append(branch)
                
                # Add a few other branches if we don't have enough
                for branch in all_branches[:3]:
                    if branch not in branches_to_check:
                        branches_to_check.append(branch)
                
                # Check if commit exists in each branch
                for branch_name in branches_to_check:
                    try:
                        commit_url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo_name}/commits/{commit_id}"
                        params = {
                            'api-version': '7.0',
                            'searchCriteria.itemVersion.version': branch_name,
                            'searchCriteria.itemVersion.versionType': 'branch'
                        }
                        
                        branch_response = self.session.get(commit_url, params=params, timeout=5)
                        if branch_response.status_code == 200:
                            branches_found.append(branch_name)
                        
                        # Only check first few branches to avoid too many API calls
                        if len(branches_found) >= 2:
                            break
                            
                    except:
                        continue
                
                if branches_found:
                    return branches_found
            
            # Fallback: return the most likely branch names
            return ['main/master']
            
        except Exception as e:
            print(f"Warning: Could not determine branch for commit {commit_id[:8]}: {e}")
            return ['main/master']
    
    def organize_commits_by_date_and_repo(self, all_commits):
        """Organize commits by date, then by repository and branch"""
        organized = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        
        for commit in all_commits:
            commit_date = datetime.fromisoformat(commit['author']['date'].replace('Z', '+00:00'))
            date_key = commit_date.strftime('%Y-%m-%d')
            repo_name = commit['repository']
            
            # Handle multiple branches
            branches = commit.get('branches', ['unknown'])
            for branch in branches:
                organized[date_key][repo_name][branch].append(commit)
        
        return organized
    
    def generate_pdf(self, organized_commits, output_filename='azure_devops_commits_report.pdf', author_filter=None):
        """Generate PDF report from organized commits"""
        doc = SimpleDocTemplate(output_filename, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        date_style = ParagraphStyle(
            'DateHeader',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            textColor=blue
        )
        
        repo_style = ParagraphStyle(
            'RepoHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=8,
            textColor=black,
            leftIndent=20
        )
        
        branch_style = ParagraphStyle(
            'BranchHeader',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            textColor=gray,
            leftIndent=40
        )
        
        commit_style = ParagraphStyle(
            'CommitStyle',
            parent=styles['Normal'],
            fontSize=9,
            leftIndent=60,
            spaceAfter=8
        )
        
        # Title
        story.append(Paragraph("Azure DevOps Commits Report", title_style))
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        if author_filter:
            story.append(Paragraph(f"Filtered by author: {author_filter}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Summary
        total_commits = sum(
            len(commits) for date_commits in organized_commits.values()
            for repo_commits in date_commits.values()
            for commits in repo_commits.values()
        )
        
        summary_data = [
            ['Total Commits', str(total_commits)],
            ['Date Range', f"{min(organized_commits.keys())} to {max(organized_commits.keys())}" if organized_commits else "No commits"],
            ['Repositories', str(len(set(repo for date_commits in organized_commits.values() for repo in date_commits.keys())))]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Organize by date (most recent first)
        sorted_dates = sorted(organized_commits.keys(), reverse=True)
        
        for date in sorted_dates:
            story.append(Paragraph(f"📅 {date}", date_style))
            
            repos = organized_commits[date]
            for repo_name in sorted(repos.keys()):
                story.append(Paragraph(f"📁 Repository: {repo_name}", repo_style))
                
                branches = repos[repo_name]
                for branch_name in sorted(branches.keys()):
                    commits = branches[branch_name]
                    story.append(Paragraph(f"🌿 Branch: {branch_name} ({len(commits)} commits)", branch_style))
                    
                    # Sort commits by time (most recent first)
                    sorted_commits = sorted(commits, 
                                          key=lambda x: datetime.fromisoformat(x['author']['date'].replace('Z', '+00:00')), 
                                          reverse=True)
                    
                    for commit in sorted_commits:
                        commit_time = datetime.fromisoformat(commit['author']['date'].replace('Z', '+00:00'))
                        time_str = commit_time.strftime('%H:%M:%S')
                        
                        # Truncate long commit messages
                        message = commit['comment'].strip().replace('\n', ' ')[:100]
                        if len(commit['comment'].strip()) > 100:
                            message += "..."
                        
                        commit_text = f"""
                        <b>{time_str}</b> - {message}<br/>
                        <i>Author:</i> {commit['author']['name']} &lt;{commit['author']['email']}&gt;<br/>
                        <i>Commit ID:</i> <font color="blue">{commit['commitId'][:8]}</font>
                        """
                        
                        story.append(Paragraph(commit_text, commit_style))
                
                story.append(Spacer(1, 12))
            
            story.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(story)
        print(f"PDF report generated: {output_filename}")

def main():
    parser = argparse.ArgumentParser(description='Generate PDF report of Azure DevOps commits')
    parser.add_argument('--config', help='JSON config file with repositories and tokens')
    parser.add_argument('--author', help='Filter commits by author email or name (e.g., your.email@company.com or "Your Name")')
    parser.add_argument('--no-branches', action='store_true', help='Skip branch detection for faster processing')
    parser.add_argument('--days', type=int, default=30, help='Number of days back to fetch commits (default: 30)')
    parser.add_argument('--output', default='azure_devops_commits_report.pdf', help='Output PDF filename')
    
    args = parser.parse_args()
    
    # If no config file provided, prompt for manual input
    if not args.config:
        print("No config file provided. Please enter repository details manually.")
        repos_config = []
        
        while True:
            repo_url = input("\nEnter Azure DevOps repository URL (or 'done' to finish): ").strip()
            if repo_url.lower() == 'done':
                break
            
            token = input("Enter Personal Access Token for this repository: ").strip()
            
            repos_config.append({
                'url': repo_url,
                'token': token
            })
        
        if not repos_config:
            print("No repositories configured. Exiting.")
            sys.exit(1)
        
        # Get author filter if not provided via command line
        if not args.author:
            author_input = input("\nEnter your email or name to filter commits (leave empty for all commits): ").strip()
            if author_input:
                args.author = author_input
    else:
        # Load from config file
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
                repos_config = config.get('repositories', [])
        except FileNotFoundError:
            print(f"Config file {args.config} not found.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Invalid JSON in config file {args.config}")
            sys.exit(1)
    
    # Fetch commits
    fetcher = AzureDevOpsCommitsFetcher()
    all_commits = []
    
    for repo_config in repos_config:
        commits = fetcher.fetch_commits(
            repo_config['url'], 
            repo_config['token'], 
            args.days, 
            skip_branches=getattr(args, 'no_branches', False),
            author_filter=args.author
        )
        all_commits.extend(commits)
    
    if not all_commits:
        print("No commits found in the specified repositories and time range.")
        sys.exit(1)
    
    # Organize and generate PDF
    organized_commits = fetcher.organize_commits_by_date_and_repo(all_commits)
    fetcher.generate_pdf(organized_commits, args.output, author_filter=args.author)
    
    print(f"\nReport generated successfully!")
    print(f"Total commits processed: {len(all_commits)}")
    print(f"Output file: {args.output}")

if __name__ == "__main__":
    main()


# RUN CMD : -> python3 git_rep_gen.py --config repos_config.json --days 30 --output my_commits.pdf --author "raunakraj94543"