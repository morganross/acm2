import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

commands = [
    # Step 1: Create temp directory
    'rm -rf /tmp/acm2-temp && mkdir -p /tmp/acm2-temp',
    
    # Step 2: Clone backend repo
    'cd /tmp/acm2-temp && git clone https://github.com/morganross/acm2.git',
    
    # Step 3: Check if plugin folder is a git repo
    'ls -la /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/.git 2>/dev/null && echo "IS A GIT REPO" || echo "NOT A GIT REPO"',
    
    # Step 4: Copy ui folder to plugin directory
    'cp -r /tmp/acm2-temp/acm2/acm2/ui /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/',
    
    # Step 5: Verify copy
    'ls -la /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui/',
    
    # Step 6: Git status
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git status',
    
    # Step 7: Git add
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git add ui/',
    
    # Step 8: Git commit
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git commit -m "Add React UI source from backend repo"',
    
    # Step 9: Git push
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git push origin main',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"$ {cmd}")
    print('='*60)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\n\nDone!")
