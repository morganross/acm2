import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

PLUGIN_DIR = '/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin'

commands = [
    # Step 1: Update vite.config.ts to output to assets/react-build with correct filenames
    f'''cat > {PLUGIN_DIR}/ui/vite.config.ts << 'EOF'
import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({{
  plugins: [react()],
  resolve: {{
    alias: {{
      '@': path.resolve(__dirname, './src'),
    }},
  }},
  base: './',
  build: {{
    outDir: '../assets/react-build',
    emptyOutDir: true,
    rollupOptions: {{
      output: {{
        entryFileNames: 'assets/index-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]'
      }}
    }}
  }},
}})
EOF''',

    # Step 2: Install npm dependencies
    f'cd {PLUGIN_DIR}/ui && npm install 2>&1',
    
    # Step 3: Build the UI
    f'cd {PLUGIN_DIR}/ui && npm run build 2>&1',
    
    # Step 4: List the build output
    f'ls -la {PLUGIN_DIR}/assets/react-build/',
    f'ls -la {PLUGIN_DIR}/assets/react-build/assets/ 2>/dev/null || echo "No assets folder"',
    
    # Step 5: Remove placeholder react-app folder
    f'sudo rm -rf {PLUGIN_DIR}/react-app',
    
    # Step 6: Verify react-app is removed
    f'ls -la {PLUGIN_DIR}/',
    
    # Step 7: Git add all changes
    f'sudo -u bitnami git -C {PLUGIN_DIR} add -A',
    
    # Step 8: Git status
    f'sudo -u bitnami git -C {PLUGIN_DIR} status',
    
    # Step 9: Git commit
    f'sudo -u bitnami git -C {PLUGIN_DIR} commit -m "Build React UI, remove placeholder react-app"',
    
    # Step 10: Git push
    f'sudo -u bitnami git -C {PLUGIN_DIR} push origin main',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"$ {cmd[:80]}..." if len(cmd) > 80 else f"$ {cmd}")
    print('='*60)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)  # 5 min timeout for npm
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out[:2000])  # Truncate long output
        if len(out) > 2000:
            print(f"... (truncated, {len(out)} chars total)")
    if err:
        print(f"STDERR: {err[:1000]}")

ssh.close()
print("\n\nDone!")
