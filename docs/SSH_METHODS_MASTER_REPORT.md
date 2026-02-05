# SSH & Remote Execution: Master Reference

A consolidated guide comparing all methods for executing code on remote servers.

---

## Method Comparison Chart

| Category | Method | Complexity | Escaping Issues | Multi-Line | Best For | Copilot Safe |
|----------|--------|------------|-----------------|------------|----------|--------------|
| **Basic SSH** | Inline command | Low | Medium | No | Quick one-liners | ✅ Yes |
| **Basic SSH** | Semicolon chaining | Low | Medium | Partial | Sequential commands | ✅ Yes |
| **Basic SSH** | && conditional | Low | Medium | Partial | Dependent commands | ✅ Yes |
| **Basic SSH** | Piped commands | Low | High | No | Data processing | ✅ Yes |
| **Python** | Paramiko | Medium | None | ✅ Yes | Complex operations | ✅✅ Best |
| **File Transfer** | SCP upload | Low | None | N/A | Deploying files | ✅ Yes |
| **File Transfer** | SCP + mv | Low | None | ✅ Yes | Multi-line code | ✅✅ Best |
| **File Transfer** | Base64 encode | High | None | ✅ Yes | Binary/special chars | ✅ Yes |
| **In-Place Edit** | sed -i | Medium | High | No | Simple replacements | ⚠️ Careful |
| **In-Place Edit** | Heredoc | High | Very High | ✅ Yes | Multi-line content | ❌ Avoid |
| **Background** | isBackground=true | Low | Medium | N/A | Servers, watchers | ✅ Yes |
| **Background** | Start-Process | Low | Low | N/A | Detached processes | ✅ Yes |
| **Version Control** | Git operations | Low | Low | N/A | Code deployment | ✅ Yes |

---

## Detailed Method Analysis

### 🟢 RECOMMENDED METHODS

#### 1. SCP + Move (Best for Multi-Line Code)
```powershell
# Write locally (no escaping issues)
$code = @'
<?php
function my_function($param = null) {
    if ($param === null) {
        $param = get_current_user_id();
    }
    return do_something($param);
}
'@
$code | Out-File -Encoding utf8 C:\temp\fix.php

# Transfer to remote
scp -i ~/.ssh/key C:\temp\fix.php user@host:/tmp/

# Move into place
ssh user@host "mv /tmp/fix.php /final/path/"
```

| Pros | Cons |
|------|------|
| ✅ Zero escaping issues | ❌ Multiple steps |
| ✅ Works with any content | ❌ Requires temp files |
| ✅ Atomic deployment | ❌ Slightly slower |
| ✅ Easy to debug/verify | |
| ✅ Copilot-safe | |

**When to use:** Multi-line PHP, complex configs, any content with special characters.

---

#### 2. Python Paramiko (Best for Complex Operations)
```python
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('hostname', username='user', key_filename='/path/to/key')

cmd = """
cd /opt/bitnami/wordpress
grep -n 'function_name' wp-content/plugins/*/includes/*.php
cat /var/log/debug.log | tail -50
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
ssh.close()
```

| Pros | Cons |
|------|------|
| ✅ No shell escaping issues | ❌ Requires Python + paramiko |
| ✅ Multi-line commands natural | ❌ More setup code |
| ✅ Reusable scripts | ❌ Overkill for simple commands |
| ✅ Handles complex pipelines | |
| ✅ Separates stdout/stderr | |

**When to use:** Database queries, multi-step operations, anything with quotes/pipes/awk.

---

#### 3. Simple Inline SSH (Best for Quick Commands)
```powershell
ssh -i ~/.ssh/key user@host "cat /path/to/file.php"
ssh -i ~/.ssh/key user@host "tail -50 /var/log/debug.log"
ssh -i ~/.ssh/key user@host "grep -n 'pattern' /path/file.php"
```

| Pros | Cons |
|------|------|
| ✅ Simple, fast | ❌ Escaping issues with complex commands |
| ✅ One command = one result | ❌ Not great for multi-line |
| ✅ Easy to understand | ❌ Quotes can conflict |
| ✅ Copilot-safe | |

**When to use:** Reading files, checking status, simple greps, quick diagnostics.

---

#### 4. Background Processes (isBackground=true)
```powershell
# Copilot tool usage
run_in_terminal(
    command="ssh user@host 'nohup python server.py &'",
    isBackground=true
)
```

| Pros | Cons |
|------|------|
| ✅ Doesn't block | ❌ Can't see immediate output |
| ✅ Survives context switches | ❌ Need to check output later |
| ✅ Good for servers | ❌ Harder to debug |

**When to use:** Starting servers, watch mode builds, long-running processes.

---

### 🟡 USE WITH CAUTION

#### 5. Sed In-Place Editing
```powershell
ssh user@host "sed -i 's/old_text/new_text/g' /path/file.php"
```

| Pros | Cons |
|------|------|
| ✅ Quick single-line changes | ❌ No backup by default |
| ✅ Regex support | ❌ Escaping nightmare |
| ✅ No file transfer needed | ❌ Hard to verify before applying |
| | ❌ Can corrupt file if interrupted |

**When to use:** Simple find-replace where text is known and simple (no special chars).

---

#### 6. Heredoc via SSH
```bash
ssh user@host 'cat > /path/file.php << "EOF"
content here
EOF'
```

| Pros | Cons |
|------|------|
| ✅ Multi-line in one command | ❌ Quoting is extremely tricky |
| ✅ No temp files | ❌ PowerShell heredocs don't work via SSH |
| | ❌ Easy to get wrong |
| | ❌ Hard to debug |

**When to use:** Simple multi-line content from bash/Linux. Avoid from PowerShell.

---

### 🔴 AVOID

#### 7. Interactive SSH Sessions
```powershell
ssh user@host  # Opens interactive shell
```

| Pros | Cons |
|------|------|
| ✅ Full shell access | ❌ Hangs with Copilot |
| | ❌ Context switches break it |
| | ❌ Can't automate |
| | ❌ Gets stuck waiting for input |

**When to use:** Never with Copilot. Only for manual human use.

---

#### 8. Password Piping
```powershell
echo "password" | ssh user@host "command"  # DOESN'T WORK
```

| Pros | Cons |
|------|------|
| None | ❌ SSH ignores stdin passwords |
| | ❌ Security feature prevents this |

**When to use:** Never. Use SSH keys or Paramiko instead.

---

## Decision Flowchart

```
START
  │
  ▼
Is it a simple read/check command?
  │
  ├─YES─→ Use: ssh user@host "command"
  │
  ▼
Does it involve complex quoting/pipes/awk?
  │
  ├─YES─→ Use: Python Paramiko script
  │
  ▼
Are you writing multi-line code?
  │
  ├─YES─→ Use: Local file + SCP + mv
  │
  ▼
Is it a long-running process (server)?
  │
  ├─YES─→ Use: isBackground=true or Start-Process
  │
  ▼
Is it a simple find-replace?
  │
  ├─YES─→ Use: sed -i (with backup!)
  │
  ▼
Default: Use SCP approach (safest)
```

---

## Quick Reference: Command Templates

### Read Operations
```powershell
# View entire file
ssh -i KEY user@host "cat /path/file.php"

# View specific lines
ssh -i KEY user@host "sed -n '100,150p' /path/file.php"

# Search for pattern
ssh -i KEY user@host "grep -n 'pattern' /path/file.php"

# Search with context
ssh -i KEY user@host "grep -n -B5 -A5 'pattern' /path/file.php"

# Find files
ssh -i KEY user@host "find /path -name '*.php' -type f"
```

### Write Operations (Safe Pattern)
```powershell
# Step 1: Write locally
$content = @'
your multi-line
content here
'@
$content | Out-File -Encoding utf8 C:\temp\file.txt

# Step 2: Upload to temp
scp -i KEY C:\temp\file.txt user@host:/tmp/

# Step 3: Backup and move
ssh -i KEY user@host "cp /path/file.txt /path/file.txt.bak; mv /tmp/file.txt /path/"

# Step 4: Verify
ssh -i KEY user@host "php -l /path/file.php"  # syntax check
```

### Simple Edits (Single Line)
```powershell
# Find-replace (simple text only)
ssh -i KEY user@host "sed -i 's/oldtext/newtext/g' /path/file.php"

# Delete lines
ssh -i KEY user@host "sed -i '10,20d' /path/file.php"

# Append line
ssh -i KEY user@host "echo 'new line' >> /path/file.txt"
```

### Background Processes
```powershell
# Start server (Copilot tool)
run_in_terminal(command="...", isBackground=true)

# Start detached (PowerShell)
Start-Process -NoNewWindow python -ArgumentList "server.py"

# Remote background
ssh -i KEY user@host "nohup python server.py > /tmp/log.txt 2>&1 &"
```

---

## Escaping Reference

| Character | In PowerShell Double Quotes | In SSH Command |
|-----------|----------------------------|----------------|
| `$` | `` `$ `` | `\$` |
| `"` | `\"` or `""` | `\"` |
| `'` | Just use it | Wrap command in `"` |
| `\` | `\\` | `\\` |
| `` ` `` | ``` `` ``` | Just use it |

**Pro tip:** When escaping gets complex, switch to SCP or Paramiko.

---

## Summary: Method Rankings

| Use Case | Best Method | Runner-Up |
|----------|-------------|-----------|
| Read file content | Inline SSH | Paramiko |
| Search in files | Inline SSH (grep) | Paramiko |
| Deploy multi-line code | SCP + mv | Paramiko |
| Simple text replacement | sed -i | SCP + mv |
| Complex shell scripts | Paramiko | SCP script + execute |
| Start servers | isBackground | Start-Process |
| Database queries | Paramiko | Inline with -e flag |
| Git operations | Inline SSH | Paramiko |
| Binary files | SCP | Base64 encode |

---

## Golden Rules

1. **When in doubt, use SCP** — Zero escaping issues, atomic writes
2. **Never use interactive SSH** — Breaks Copilot context
3. **Paramiko for complexity** — Quotes, pipes, awk, multi-step
4. **Always backup before sed -i** — `cp file file.bak` first
5. **Validate after writing** — `php -l`, `python -m py_compile`, etc.
6. **Use absolute paths** — Don't rely on `cd` persisting
7. **Redirect stderr** — `2>/dev/null` or `2>&1` for clean output

---

## Live Test Results (February 5, 2026)

### Test Environment
- **Local**: Windows PowerShell on Windows Server
- **Remote**: Bitnami WordPress on AWS Lightsail (16.145.206.59)
- **Auth**: SSH key at `C:\Users\Administrator\.ssh\id_ed25519`

### PowerShell SSH Test Suite: 29/31 PASSED

| Test Category | Tests | Result |
|---------------|-------|--------|
| Inline commands | 3 | ✅ All pass |
| Semicolon chaining | 2 | ✅ All pass |
| Conditional && | 2 | ✅ All pass |
| Piped commands | 2 | ✅ All pass |
| File reading (cat/head/tail/sed/grep) | 6 | ✅ All pass |
| Echo redirect/append | 2 | ✅ All pass |
| Sed in-place edit | 2 | ✅ All pass |
| SCP upload/download | 2 | ✅ All pass |
| SCP + Move atomic | 1 | ✅ Pass |
| Backup + Edit | 1 | ✅ Pass |
| Syntax check (PHP) | 2 | ⚠️ Fail (path issue) |
| Git operations | 2 | ✅ All pass |
| Timeout handling | 1 | ✅ Pass |

**Failed tests**: PHP syntax check failed because `php` wasn't in PATH. Fix: use `/opt/bitnami/php/bin/php`.

### Python Paramiko Test Suite: 14/14 PASSED

| Test | Result |
|------|--------|
| Basic connection | ✅ |
| Multi-line commands | ✅ |
| Complex pipelines (grep\|awk\|sort) | ✅ |
| Mixed quotes handling | ✅ |
| stdout/stderr separation | ✅ |
| Exit code capture | ✅ |
| File operations (heredoc) | ✅ |
| SFTP Upload | ✅ |
| SFTP Download | ✅ |
| Database query pattern | ✅ |
| Timeout behavior | ✅ |
| Connection reuse (5 commands) | ✅ |
| Special characters ($, \`, ;, &&, \|) | ✅ |
| Cleanup | ✅ |

### Console Output Visibility: CONFIRMED

Copilot can see ALL console output including:
- Random markers (verified unique IDs returned correctly)
- PHP execution results (`PHP_OK`, `MATH_RESULT=50`)
- Error logs with timestamps
- File contents via cat/tail
- WordPress debug.log entries
- Command exit codes

### Verified Capability Matrix

| Capability | Method Tested | Result | Proof |
|------------|---------------|--------|-------|
| **Local file write** | PowerShell `echo >` | ✅ Works | Unique marker echoed back |
| **Local file write** | Python script | ✅ Works | Multi-line PHP created |
| **Local file read** | `type` / `Get-Content` | ✅ Works | Content visible |
| **Remote file write** | SSH + `echo >` | ✅ Works | `REMOTE_WRITE_999` confirmed |
| **Remote file write** | SCP upload | ✅ Works | All SCP tests passed |
| **Remote file read** | SSH + `cat` | ✅ Works | Plugin code visible |
| **Remote file read** | SSH + `tail` | ✅ Works | Debug log readable |
| **Remote file read** | SSH + `grep` | ✅ Works | Function found (count=1) |
| **Run bash code** | SSH inline | ✅ Works | Loop output: 1, 2, 3 |
| **Run PHP code** | SCP + php execute | ✅ Works | Math result: 50 |
| **See errors** | stderr capture | ✅ Works | Parse errors visible |

### Escaping Gotchas Discovered

| Scenario | What Breaks | Solution |
|----------|-------------|----------|
| PHP `-r` inline | Parentheses in code | Write to file, execute file |
| Heredoc from PowerShell | Quote nesting | Use Python to create file, SCP it |
| `$variable` in double quotes | PowerShell interpolates | Use single quotes or escape as `` `$ `` |
| Bash for loop | `$i` eaten by PowerShell | Single-quote entire SSH command |

### Proven Workflow for Code Fixes

```powershell
# 1. Create fix with Python (avoids all escaping)
py -3 -c "
fixed = '''<?php
function acm2_get_user_uuid(\$user_id = null) {
    if (\$user_id === null) {
        \$user_id = get_current_user_id();
    }
    return ACM2_User_Sync::get_or_create_user_uuid(\$user_id);
}
'''
open('C:/devlop/fix.php', 'w').write(fixed)
"

# 2. Upload to temp location
scp -i ~/.ssh/key C:\devlop\fix.php user@host:/tmp/

# 3. Backup existing file
ssh -i ~/.ssh/key user@host "cp /path/original.php /path/original.php.bak"

# 4. Apply fix (append, replace, or move)
ssh -i ~/.ssh/key user@host "cat /tmp/fix.php >> /path/original.php"

# 5. Validate
ssh -i ~/.ssh/key user@host "/opt/bitnami/php/bin/php -l /path/original.php"

# 6. Verify content
ssh -i ~/.ssh/key user@host "tail -20 /path/original.php"
```

### Test Scripts Location

- **PowerShell tests**: `docs/test-ssh-methods.ps1`
- **Paramiko tests**: `docs/test-paramiko-methods.py`

Run them with:
```powershell
# PowerShell suite (31 tests)
powershell -ExecutionPolicy Bypass -File docs\test-ssh-methods.ps1

# Python Paramiko suite (14 tests)
py -3 docs\test-paramiko-methods.py
```
