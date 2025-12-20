#!/usr/bin/env python3
"""Verify Default Preset has all required fields configured."""

import sqlite3

db_path = "C:/Users/kjhgf/.acm2/acm2.db"

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
SELECT 
    name, 
    pairwise_enabled, 
    post_combine_top_n, 
    eval_iterations, 
    fpf_log_output, 
    generation_concurrency, 
    eval_concurrency, 
    request_timeout, 
    eval_timeout,
    max_retries,
    retry_delay,
    iterations,
    fpf_log_file_path
FROM presets 
WHERE name = 'Default Preset'
""")

row = c.fetchone()
if row:
    print(f"✅ Default Preset Configuration:")
    print(f"   Name: {row[0]}")
    print(f"   pairwise_enabled: {row[1]}")
    print(f"   post_combine_top_n: {row[2]}")
    print(f"   eval_iterations: {row[3]}")
    print(f"   fpf_log_output: {row[4]}")
    print(f"   generation_concurrency: {row[5]}")
    print(f"   eval_concurrency: {row[6]}")
    print(f"   request_timeout: {row[7]}")
    print(f"   eval_timeout: {row[8]}")
    print(f"   max_retries: {row[9]}")
    print(f"   retry_delay: {row[10]}")
    print(f"   iterations: {row[11]}")
    print(f"   fpf_log_file_path: {row[12]}")
    
    print("\n🔍 Validation:")
    issues = []
    if row[1] != 1:
        issues.append("❌ pairwise_enabled should be 1 (True)")
    if row[2] is None:
        issues.append("❌ post_combine_top_n is None - post-combine eval will NOT run!")
    elif row[2] < 2:
        issues.append(f"❌ post_combine_top_n is {row[2]}, must be >= 2")
    else:
        print(f"   ✅ post_combine_top_n = {row[2]} (post-combine eval ENABLED)")
    
    if row[3] is None or row[3] < 1:
        issues.append(f"❌ eval_iterations is {row[3]}, must be >= 1")
    if row[4] not in ['stream', 'file', 'none']:
        issues.append(f"❌ fpf_log_output is '{row[4]}', must be stream/file/none")
    if row[5] is None or row[5] < 1:
        issues.append(f"❌ generation_concurrency is {row[5]}, must be >= 1")
    if row[6] is None or row[6] < 1:
        issues.append(f"❌ eval_concurrency is {row[6]}, must be >= 1")
    if row[7] is None or row[7] < 60:
        issues.append(f"❌ request_timeout is {row[7]}, must be >= 60")
    if row[8] is None or row[8] < 60:
        issues.append(f"❌ eval_timeout is {row[8]}, must be >= 60")
    
    if issues:
        print("\n❌ ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("   ✅ All fields valid!")
        print("\n🎯 VERIFIED: Post-combine evaluation WILL run with this preset!")
else:
    print("❌ Default Preset not found!")

conn.close()
