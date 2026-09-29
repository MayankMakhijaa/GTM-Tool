# Fameweb --- Database Schema

## 1. user_table

Core account. - user_id PK - name - email_id UNIQUE - phone_no UNIQUE -
password_hash - email_verified_at - onboarding_step -
optimization_status - is_active - created_at - updated_at

## 2. users_company_details

One company record per user. - id PK - user_id FK UNIQUE -
company_name - website_url - description - what_company_sells -
products_services - industry - company_size - revenue - location -
rating - other_details - scrape_status - edited_fields JSON -
scraped_at - created_at - updated_at

## 3. users_icp

One ICP record per user. - id PK - user_id FK UNIQUE - target_customer -
company_size - revenue_range - target_jobs_roles - industry - location -
keywords JSON - exclusions JSON - signals JSON - tone - summary_report
JSON - version - created_at - updated_at

## 4. users_linkedin_details

One LinkedIn profile record per user. - id PK - user_id FK UNIQUE -
oidc_sub UNIQUE nullable - linkedin_id UNIQUE nullable - profile_url -
name - headline - about - current_position - location - experience
JSON - education JSON - skills JSON - profile_data JSON -
profile_source - profile_completeness - optimization_suggestions JSON -
auth_data_encrypted - connection_status - consent_at -
last_verified_at - last_used_at - created_at - updated_at

## 5. global_profiles

Shared/global facts only. - global_id PK - linkedin_id UNIQUE -
profile_url - name - role - headline - company - location - industry -
company_data JSON - source - do_not_contact - recommended_no_of_times -
last_updated - created_at

## 6. users_profiles

User-specific relationship and qualification. - id PK - user_id FK -
global_id FK - research_job_id FK nullable - research_source -
match_score - qualification_reason - lead_status - icp_version -
first_seen_at - last_seen_at - created_at - updated_at - UNIQUE(user_id,
global_id)

## 7. research_jobs

Persistent research execution state. - id PK - user_id FK - status -
research_type - icp_version - budget JSON - progress JSON -
stop_reason - results_count - error_message - attempts - heartbeat_at -
started_at - completed_at - created_at - updated_at

Partial unique index: one active job per user for QUEUED/RUNNING/PAUSED.

## 8. connect_and_message

One outreach thread per user + prospect. - id PK - user_id FK -
global_id FK - connection_status - connection_message - messages JSON -
follow_up_status - next_follow_up_at - version -
connection_requested_at - accepted_at - last_activity_at - created_at -
updated_at - UNIQUE(user_id, global_id)

## Message JSON

Each message contains: - id - sequence - sender: USER \| LEAD - type:
CONNECTION \| MESSAGE \| REPLY \| FOLLOW_UP - message - status -
scheduled_at - sent_at - sent_via - generated_by - model - error -
created_at

Messages are appended, never overwritten as a conversation.
