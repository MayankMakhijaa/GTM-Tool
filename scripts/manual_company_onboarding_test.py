#!/usr/bin/env python3
"""
Manual End-to-End Company Discovery and Crawl4AI Scraping Test Script.

Usage:
    .venv\\Scripts\\python.exe scripts\\manual_company_onboarding_test.py
    .venv\\Scripts\\python.exe scripts\\manual_company_onboarding_test.py alex@acme.com
    .venv\\Scripts\\python.exe scripts\\manual_company_onboarding_test.py --verbose
    .venv\\Scripts\\python.exe scripts\\manual_company_onboarding_test.py alex@acme.com --verbose

No database writes are performed. All SSRF and security controls are enforced.
"""

import sys
import os
import io
import re
import json
import logging
import textwrap
import argparse
import contextlib
from typing import Dict, Any, Optional

from app.services.company_discovery_service import identify_company_from_email
from app.services.scraping_service import scrape_official_company_website


def is_valid_email(email: str) -> bool:
    """Validates email format using regex."""
    if not email or not isinstance(email, str):
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


def configure_logging(verbose: bool):
    """Configures logging level and environment flags for verbose or normal (silent) mode."""
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.CRITICAL)
        os.environ["CRAWL4AI_VERBOSE"] = "false"
        # Suppress noisy third-party loggers
        for logger_name in [
            "app",
            "app.services",
            "app.services.company_discovery_service",
            "app.services.scraping_service",
            "google_genai",
            "httpx",
            "urllib3",
            "crawl4ai",
            "asyncio",
            "google",
        ]:
            log = logging.getLogger(logger_name)
            log.setLevel(logging.CRITICAL)
            log.disabled = True


@contextlib.contextmanager
def suppress_output_in_normal_mode(verbose: bool):
    """Context manager to suppress stdout/stderr output during scraping in normal mode."""
    if not verbose:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        devnull = io.StringIO()
        try:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    else:
        yield


def print_title_header():
    print("========================================")
    print("       FAMEWEB COMPANY DATA EXTRACTOR   ")
    print("========================================\n")


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f" {title}")
    print("=" * 75)


def get_email_input(cli_email: Optional[str] = None) -> str:
    """Gets business email from CLI argument or interactive user prompt."""
    if cli_email and is_valid_email(cli_email):
        return cli_email.strip()

    if cli_email and not is_valid_email(cli_email):
        print(f"Error: Invalid email address provided: '{cli_email}'\n")

    while True:
        try:
            email = input("Enter your business email: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled by user.")
            sys.exit(0)

        if is_valid_email(email):
            return email
        print("Invalid email format. Please enter a valid business email address (e.g., alex@company.com).\n")


def format_company_profile_table(scraped_data: Dict[str, Any]) -> str:
    """Formats consolidated company data into a clean, aligned table with word wrapping."""
    fields = [
        ("Company Name", scraped_data.get("company_name")),
        ("Website URL", scraped_data.get("website_url")),
        ("Description", scraped_data.get("description")),
        ("What Company Sells", scraped_data.get("what_company_sells")),
        ("Products / Services", scraped_data.get("products_services")),
        ("Industry", scraped_data.get("industry")),
        ("Company Size", scraped_data.get("company_size")),
        ("Revenue", scraped_data.get("revenue")),
        ("Location", scraped_data.get("location")),
        ("Rating", scraped_data.get("rating")),
        ("Other Details", scraped_data.get("other_details")),
    ]

    lines = []
    lines.append("========================================")
    lines.append("          COMPANY PROFILE               ")
    lines.append("========================================\n")

    max_label_width = 19

    for label, val in fields:
        if val is None or val == "" or (isinstance(val, list) and len(val) == 0):
            val_str = "Not available"
        elif isinstance(val, list):
            val_str = ", ".join([str(x).strip() for x in val if x and str(x).strip()])
            if not val_str:
                val_str = "Not available"
        else:
            val_str = str(val).strip()

        wrapped_lines = textwrap.wrap(val_str, width=60)
        if not wrapped_lines:
            wrapped_lines = ["Not available"]

        label_part = label.ljust(max_label_width)
        lines.append(f"{label_part}| {wrapped_lines[0]}")
        for continuation in wrapped_lines[1:]:
            lines.append(f"{' ' * max_label_width}| {continuation}")

    lines.append("\n========================================")
    lines.append("       EXTRACTION COMPLETED             ")
    lines.append("========================================")

    return "\n".join(lines)


def run_manual_onboarding(email: str, verbose: bool = False):
    if verbose:
        print_banner(f"STEP 2: COMPANY DOMAIN IDENTIFICATION FOR: {email}")
    else:
        print("Identifying company...")

    # 1. Execute Step 2 Identification
    try:
        with suppress_output_in_normal_mode(verbose):
            id_res = identify_company_from_email(email)
    except Exception as e:
        if verbose:
            raise
        print(f"\n[ERROR] Company identification error: {str(e)}")
        return

    domain = id_res.get("email_domain")
    company_name = id_res.get("company_name")
    official_website = id_res.get("official_website")
    status = id_res.get("identification_status")
    requires_conf = id_res.get("requires_user_confirmation")
    msg = id_res.get("message")

    if verbose:
        print(f"Extracted Email Domain : {domain or 'N/A'}")
        print(f"Identified Company Name: {company_name or 'N/A'}")
        print(f"Official Website URL   : {official_website or 'N/A'}")
        print(f"Identification Status  : {status}")
        print(f"User Confirmation Req. : {requires_conf}")
        print(f"Discovery Message      : {msg}")

    confirmed_by_user = False

    if status == "CONFIRMED":
        if verbose:
            print("\n[SUCCESS] Company identity confidently established.")
        confirmed_by_user = True

    elif status == "NEEDS_CONFIRMATION":
        print(f"\nCompany domain identification requires confirmation:")
        print(f"  Proposed Company Name : {company_name or 'Unknown'}")
        print(f"  Proposed Official Site: {official_website or 'N/A'}")

        try:
            user_input = input("\nDo you confirm this is your company's official website? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            user_input = "n"

        if user_input in ("y", "yes"):
            if verbose:
                print("[CONFIRMED] User confirmed the company website.")
            confirmed_by_user = True
        else:
            print("\n[ABORTED] Website confirmation declined by user.")
            return

    elif status in ("NOT_FOUND", "FAILED"):
        print(f"\n[ERROR] Company identification ended with status: {status}")
        print(f"Reason: {msg}")
        return

    # 2. Execute Step 3 Crawl4AI Scraping Service & Gemini Enrichment
    if verbose:
        print_banner(f"STEP 3: CRAWL4AI SCRAPING FOR: {official_website}")
        print("[INFO] Launching Crawl4AI AsyncWebCrawler with Playwright headless browser...")
        print("[INFO] SSRF IP guards, domain restrictions, and bounded page limits active.")
    else:
        print("Scraping website and enriching company data...")
        print("Preparing final profile...\n")

    try:
        with suppress_output_in_normal_mode(verbose):
            scrape_res = scrape_official_company_website(
                website_url=official_website,
                identification_status=status,
                requires_user_confirmation=requires_conf,
                confirmed_by_user=confirmed_by_user,
            )
    except Exception as e:
        if verbose:
            raise
        print(f"\n[ERROR] Scraping execution error: {str(e)}")
        return

    if verbose:
        print_banner("FINAL SCRAPING SUMMARY")
        print(f"Scraping Status : {scrape_res.get('status')}")
        print(f"Status Message  : {scrape_res.get('message')}")
        if scrape_res.get("warnings"):
            print(f"Warnings        : {scrape_res.get('warnings')}")
        print(f"Source URLs     : {scrape_res.get('source_urls')}")

        print("\n--- TWO-PASS EXTRACTION DIAGNOSTICS ---")
        diag = scrape_res.get("diagnostics", {})
        if diag:
            print(f"Extraction Engine Used   : {diag.get('extraction_engine_used')}")
            print(f"Gemini Configured        : {diag.get('gemini_configured')}")
            print(f"Gemini Request Successful: {diag.get('gemini_request_successful')}")
            print(f"Model Used               : {diag.get('model_used')}")
            print(f"Populated Fields Count   : {diag.get('populated_fields_count')}")
            if diag.get("fallback_reason"):
                print(f"Fallback Reason          : {diag.get('fallback_reason')}")
            print(f"Crawl Engine             : {diag.get('crawl_engine')}")
            print(f"Initial URL              : {diag.get('initial_url')}")
            print(f"HTTP Status              : {diag.get('http_status')}")
            print(f"Content Type             : {diag.get('content_type')}")
            print(f"Pages Crawled            : {diag.get('pages_crawled')}")
            print(f"Total Chars Extracted    : {diag.get('total_characters_extracted')}")
            print(f"Extraction Sources       : {', '.join(diag.get('extraction_sources', []))}")
            print(f"Final Extraction Status  : {diag.get('final_status')}")

            multi_diag = diag.get("multi_source_research", {})
            if multi_diag:
                print("\n--- MULTI-SOURCE & PASS 2 ENRICHMENT TELEMETRY ---")
                print(f"Research Executed        : {multi_diag.get('research_executed')}")
                print(f"Missing Before Research  : {multi_diag.get('missing_fields_before_research')}")
                print(f"Google Places Status     : {multi_diag.get('google_places_status')}")
                print(f"Search Queries Executed  : {multi_diag.get('search_queries_executed')}")
                print(f"Fields Enriched in Pass 2: {multi_diag.get('fields_enriched')}")
                print(f"Fields Remaining Missing : {multi_diag.get('missing_fields_after_research')}")

        print("\n--- CONSOLIDATED MERGED COMPANY PROFILE (RAW JSON) ---")
        scraped_data = scrape_res.get("scraped_data")
        if scraped_data:
            print(json.dumps(scraped_data, indent=2, ensure_ascii=False))

            print("\n--- FIELD-LEVEL PROVENANCE & CONFIDENCE MATRIX ---")
            prov = scraped_data.get("provenance") if isinstance(scraped_data, dict) else None
            if isinstance(prov, dict):
                for field, meta in prov.items():
                    if isinstance(meta, dict):
                        status_flag = meta.get("verification_status", "N/A")
                        src_type = meta.get("source_type", "N/A")
                        conf = meta.get("confidence", "N/A")
                        is_est = meta.get("is_estimate", False)
                        val_str = meta.get("value") if meta.get("value") is not None else "null"
                        ts = meta.get("retrieval_timestamp") or "N/A"
                        est_label = "(Estimate/Inferred)" if is_est else "(Verified Fact)"
                        print(f"  [{status_flag}] {field}: {val_str} {est_label}")
                        print(f"      Source Type : {src_type} | Confidence: {conf}")
                        print(f"      Source Name : {meta.get('source_name') or 'N/A'}")
                        print(f"      Source URL  : {meta.get('source_url') or 'N/A'}")
                        print(f"      Timestamp   : {ts}")
                        print(f"      Evidence    : {meta.get('evidence') or 'N/A'}")

        print("\n" + "-" * 75)
        print("[SAFETY CONFIRMATION] No database writes were performed (PostgreSQL untouched).")
        print("[SAFETY CONFIRMATION] Surgical Gemini Two-Pass Enrichment completed safely.")
        print("-" * 75 + "\n")

    # 3. Print Final Consolidated Profile Table
    scraped_data = scrape_res.get("scraped_data")
    if scrape_res.get("status") in ("SUCCESS", "PARTIAL") and scraped_data:
        table_output = format_company_profile_table(scraped_data)
        print(table_output)
    else:
        err_msg = scrape_res.get("message") or "Failed to extract usable company data."
        print(f"[ERROR] {err_msg}")


def main():
    parser = argparse.ArgumentParser(
        description="Fameweb Manual Company Onboarding & Data Extraction Test Runner"
    )
    parser.add_argument("email", nargs="?", default=None, help="Business email address (e.g. alex@company.com)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose technical diagnostics and telemetry")

    args = parser.parse_args()

    configure_logging(args.verbose)

    print_title_header()

    email = get_email_input(args.email)

    run_manual_onboarding(email, verbose=args.verbose)


if __name__ == "__main__":
    main()
