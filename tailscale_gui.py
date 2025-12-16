#!/usr/bin/env python3
"""
Tailscale GUI Controller for Ubuntu
A Linux GUI application to control Tailscale, switch accounts, and view devices.
"""

__version__ = "1.11.2"

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio, Gdk
import subprocess
import json
import threading
import os
from pathlib import Path

class TailscaleController:
    """Handles Tailscale CLI operations"""
    
    def __init__(self):
        self.tailscale_cmd = 'tailscale'
        self.config_dir = Path.home() / '.config' / 'tailscale-gui'
        self.profiles_file = self.config_dir / 'profiles.json'
        self.check_tailscale_installed()
        self.ensure_config_dir()
    
    def ensure_config_dir(self):
        """Ensure config directory exists"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def save_profiles(self, profiles):
        """Save profiles to config file"""
        try:
            with open(self.profiles_file, 'w') as f:
                json.dump(profiles, f, indent=2)
            return True
        except Exception:
            return False
    
    def load_profiles(self):
        """Load profiles from config file"""
        try:
            if self.profiles_file.exists():
                with open(self.profiles_file, 'r') as f:
                    profiles = json.load(f)
                    # Ensure it's a list
                    if isinstance(profiles, list):
                        return profiles
            return []
        except Exception:
            return []
    
    def add_profile(self, nickname):
        """Add a new profile nickname"""
        profiles = self.load_profiles()
        # Check if already exists
        if nickname not in profiles:
            profiles.append(nickname)
            return self.save_profiles(profiles)
        return False  # Already exists
    
    def remove_profile(self, nickname):
        """Remove a profile nickname"""
        profiles = self.load_profiles()
        if nickname in profiles:
            profiles.remove(nickname)
            return self.save_profiles(profiles)
        return False
    
    def check_tailscale_installed(self):
        """Check if Tailscale is installed"""
        try:
            subprocess.run([self.tailscale_cmd, 'version'], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Tailscale is not installed. Please install it first.")
    
    def check_daemon_running(self):
        """Check if tailscaled daemon is running"""
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'is-active', 'tailscaled'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return True
            # Try system-wide service
            result = subprocess.run(
                ['systemctl', 'is-active', 'tailscaled'],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            # If systemctl fails, try checking via tailscale status
            try:
                result = subprocess.run(
                    [self.tailscale_cmd, 'status'],
                    capture_output=True,
                    timeout=2
                )
                return True  # If command runs, daemon is likely running
            except:
                return False
    
    def check_operator_permission(self):
        """Check if current user has operator permission"""
        try:
            # Try to run a command that requires operator permission
            result = subprocess.run(
                [self.tailscale_cmd, 'status'],
                capture_output=True,
                text=True,
                timeout=2
            )
            # If status works, try whoami which also needs permission
            result = subprocess.run(
                [self.tailscale_cmd, 'whoami'],
                capture_output=True,
                text=True,
                timeout=2
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
    
    def get_operator_setup_command(self):
        """Get the command to set operator permission"""
        import os
        username = os.environ.get('USER', 'your-username')
        return f"sudo tailscale set --operator={username}"
    
    def get_status(self):
        """Get current Tailscale status"""
        try:
            result = subprocess.run(
                [self.tailscale_cmd, 'status', '--json'],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            return None
    
    def is_connected(self):
        """Check if Tailscale is connected"""
        try:
            status = self.get_status()
            if not status:
                return False
            # Check if BackendState is Running and we have a node key (authenticated)
            backend_state = status.get('BackendState', '')
            have_node_key = status.get('HaveNodeKey', False)
            auth_url = status.get('AuthURL', '')
            # Connected if backend is running, has node key, and no auth URL (meaning already authenticated)
            return backend_state == 'Running' and have_node_key and auth_url == ''
        except Exception:
            return False
    
    def get_current_user(self):
        """Get current logged-in user from status"""
        try:
            status = self.get_status()
            if not status or 'Self' not in status:
                return None
            # Try to get user info from Self
            self_info = status['Self']
            # Check if there's a DNS name that might contain user info
            dns_name = self_info.get('DNSName', '')
            # The DNS name format is usually: hostname.tailXXXXX.ts.net
            # We can't easily get the email from status, but we can show the hostname
            hostname = self_info.get('HostName', '')
            if hostname:
                return hostname
            # Fallback: try to extract from DNS name
            if dns_name:
                parts = dns_name.split('.')
                if len(parts) > 0:
                    return parts[0]
            return "Connected"
        except Exception:
            return None
    
    def get_devices(self):
        """Get list of devices from Tailscale status"""
        status = self.get_status()
        if not status:
            return []
        
        devices = []
        if 'Self' in status:
            self_info = status['Self']
            devices.append({
                'name': self_info.get('DNSName', 'Unknown'),
                'ip': self_info.get('TailscaleIPs', ['Unknown'])[0] if self_info.get('TailscaleIPs') else 'Unknown',
                'online': True,
                'is_self': True
            })
        
        if 'Peer' in status:
            for peer_id, peer_info in status['Peer'].items():
                devices.append({
                    'name': peer_info.get('DNSName', 'Unknown'),
                    'ip': peer_info.get('TailscaleIPs', ['Unknown'])[0] if peer_info.get('TailscaleIPs') else 'Unknown',
                    'online': peer_info.get('Online', False),
                    'is_self': False
                })
        
        return devices
    
    def switch_account(self):
        """Switch to a different Tailscale account (logout then up)"""
        try:
            # Check if daemon is running
            if not self.check_daemon_running():
                return False, "Tailscale daemon is not running. Please start it with: sudo systemctl start tailscaled"
            
            # Check if there are multiple accounts available
            available_accounts = self.get_available_accounts()
            
            # Logout first if currently logged in
            if self.is_connected():
                try:
                    result = subprocess.run(
                        [self.tailscale_cmd, 'logout'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    # Wait a moment for logout to complete
                    import time
                    time.sleep(1)
                except subprocess.TimeoutExpired:
                    return False, "Logout timed out"
                except subprocess.CalledProcessError as e:
                    # Logout might fail, but continue anyway
                    pass
            
            # Now use tailscale up - this will connect and prompt for auth if needed
            # If multiple accounts exist, it should allow selecting
            return self._do_login()
        except FileNotFoundError:
            return False, "Tailscale command not found. Is Tailscale installed?"
        except Exception as e:
            return False, f"Error switching account: {str(e)}"
    
    def login(self):
        """Login to Tailscale (opens browser for authentication)"""
        try:
            # Check if daemon is running
            if not self.check_daemon_running():
                return False, "Tailscale daemon is not running. Please start it with: sudo systemctl start tailscaled"
            
            # If already connected, we don't need to login - just refresh
            if self.is_connected():
                current_user = self.get_current_user()
                if current_user:
                    return True, f"Already connected as {current_user}. Click 'Switch Account' to change accounts."
                return True, "Already connected to Tailscale. Click 'Switch Account' to change accounts."
            
            # Not connected, proceed with login
            return self._do_login()
            
        except FileNotFoundError:
            return False, "Tailscale command not found. Is Tailscale installed?"
        except Exception as e:
            return False, f"Error logging in: {str(e)}"
    
    def _do_login(self):
        """Internal method to perform the actual login using tailscale up"""
        try:
            # Use tailscale up instead of login - this connects and triggers auth if needed
            import os
            env = os.environ.copy()
            # Ensure DISPLAY is set for GUI apps
            if 'DISPLAY' not in env:
                env['DISPLAY'] = ':0'
            
            process = subprocess.Popen(
                [self.tailscale_cmd, 'up'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=True
            )
            
            # Wait a moment to see if it fails immediately
            import time
            time.sleep(0.8)
            
            # Check if process exited (which would indicate an error)
            if process.poll() is not None:
                # Process exited, get error message
                stdout, stderr = process.communicate()
                error_msg = ""
                if stderr:
                    error_msg = stderr.decode('utf-8', errors='ignore').strip()
                if stdout and not error_msg:
                    # Sometimes errors go to stdout
                    stdout_msg = stdout.decode('utf-8', errors='ignore').strip()
                    if "denied" in stdout_msg.lower() or "access" in stdout_msg.lower():
                        error_msg = stdout_msg
                
                if error_msg:
                    # Check for permission denied error (various formats)
                    error_lower = error_msg.lower()
                    if any(phrase in error_lower for phrase in ["access denied", "profiles access denied", "permission denied", "operator"]):
                        import os
                        username = os.environ.get('USER', 'your-username')
                        return False, f"Permission denied.\n\nIf you haven't run it yet, execute:\nsudo tailscale set --operator={username}\n\nIf you already ran that command, you MUST restart the Tailscale service:\nsudo systemctl restart tailscaled\n\nThen try logging in again."
                    return False, f"Connection failed: {error_msg}"
                return False, "Connection process exited unexpectedly. Try running 'tailscale up' in a terminal to see the error."
            
            # Process is running (waiting for browser authentication if needed) - success
            return True, "Connecting to Tailscale. Please complete authentication in your browser if prompted."
            
        except Exception as e:
            return False, f"Error during connection: {str(e)}"
    
    def get_available_accounts(self):
        """Get list of available Tailscale accounts from status"""
        try:
            status = self.get_status()
            if not status:
                return []
            
            accounts = set()
            # Get current account
            if 'Self' in status and 'UserID' in status['Self']:
                accounts.add(status['Self']['UserID'])
            
            # Get accounts from peers
            if 'Peer' in status:
                for peer_id, peer_info in status['Peer'].items():
                    if 'UserID' in peer_info:
                        accounts.add(peer_info['UserID'])
            
            return list(accounts)
        except Exception:
            return []
    
    def switch_to_profile(self, profile_name, sudo_password=None):
        """Switch to a specific Tailscale profile/nickname"""
        try:
            # Check if daemon is running
            if not self.check_daemon_running():
                return False, "Tailscale daemon is not running. Please start it with: sudo systemctl start tailscaled"
            
            # Try without sudo first (will work if operator permissions are set)
            result = subprocess.run(
                [self.tailscale_cmd, 'switch', profile_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, f"Switched to profile: {profile_name}"
            
            # If it failed, try with sudo (will work if passwordless sudo is configured)
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            
            # Try sudo without password first (if passwordless sudo is configured)
            sudo_result = subprocess.run(
                ['sudo', '-n', self.tailscale_cmd, 'switch', profile_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if sudo_result.returncode == 0:
                return True, f"Switched to profile: {profile_name}"
            
            # If both failed, we need password
            error_lower = error_msg.lower() if error_msg else ""
            if "Access denied" in error_lower or "profiles access denied" in error_lower or "failed to switch" in error_lower:
                return None, "sudo_required"
            
            # If we got here with an error, still try password prompt
            return None, "sudo_required"
        except subprocess.TimeoutExpired:
            return False, "Switch operation timed out"
        except FileNotFoundError:
            return False, "Tailscale command not found. Is Tailscale installed?"
        except Exception as e:
            return False, f"Error switching profile: {str(e)}"
    
    def switch_to_profile_with_sudo(self, profile_name, sudo_password):
        """Switch to profile using sudo with provided password"""
        try:
            # Use sudo with password via stdin
            # Note: -S flag tells sudo to read password from stdin
            process = subprocess.Popen(
                ['sudo', '-S', self.tailscale_cmd, 'switch', profile_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )
            
            # Send password followed by newline, then wait for completion
            password_input = sudo_password + '\n'
            stdout, stderr = process.communicate(input=password_input, timeout=15)
            
            # Clear password from memory (best effort)
            password_input = None
            
            if process.returncode == 0:
                return True, f"Switched to profile: {profile_name}"
            else:
                error_msg = stderr.strip() if stderr else stdout.strip()
                if not error_msg:
                    error_msg = f"Command failed with return code {process.returncode}"
                
                error_lower = error_msg.lower()
                if "password" in error_lower and ("incorrect" in error_lower or "wrong" in error_lower):
                    return False, "Incorrect sudo password. Please try again."
                elif "sorry" in error_lower or "try again" in error_lower:
                    return False, "Sudo authentication failed. Please try again."
                return False, f"Failed to switch: {error_msg}"
        except subprocess.TimeoutExpired:
            process.kill()
            return False, "Switch operation timed out"
        except Exception as e:
            return False, f"Error switching profile: {str(e)}"
    
    def logout(self):
        """Disconnect from Tailscale (tailscale down)"""
        try:
            subprocess.run(
                [self.tailscale_cmd, 'down'],
                capture_output=True,
                check=True
            )
            return True, "Tailscale disconnected successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Error disconnecting: {e.stderr}"
    
    def get_available_exit_nodes(self):
        """Get list of available exit nodes from status"""
        try:
            status = self.get_status()
            if not status:
                return []
            
            exit_nodes = []
            
            # Check Self (current device)
            if 'Self' in status:
                self_info = status['Self']
                dns_name = self_info.get('DNSName', '')
                ip = self_info.get('TailscaleIPs', [''])[0] if self_info.get('TailscaleIPs') else ''
                node_id = self_info.get('ID', '')
                
                # Check if self can be an exit node using ExitNodeOption field
                # This is the most reliable way to detect exit node capability
                can_be_exit_node = self_info.get('ExitNodeOption', False)
                
                # Only include if it can be an exit node
                if dns_name and ip and can_be_exit_node:
                    exit_nodes.append({
                        'id': node_id,
                        'name': dns_name,
                        'ip': ip,
                        'hostname': self_info.get('HostName', dns_name.split('.')[0] if dns_name else ''),
                        'is_self': True,
                        'online': True,
                        'can_be_exit_node': can_be_exit_node
                    })
            
            # Check Peers (other devices)
            if 'Peer' in status:
                for peer_id, peer_info in status['Peer'].items():
                    dns_name = peer_info.get('DNSName', '')
                    ip = peer_info.get('TailscaleIPs', [''])[0] if peer_info.get('TailscaleIPs') else ''
                    
                    # Check if peer can be an exit node using ExitNodeOption field
                    # This is the most reliable way to detect exit node capability
                    can_be_exit_node = peer_info.get('ExitNodeOption', False)
                    
                    # Only include if it can be an exit node
                    if dns_name and ip and can_be_exit_node:
                        exit_nodes.append({
                            'id': peer_id,
                            'name': dns_name,
                            'ip': ip,
                            'hostname': peer_info.get('HostName', dns_name.split('.')[0] if dns_name else ''),
                            'is_self': False,
                            'online': peer_info.get('Online', False),
                            'can_be_exit_node': can_be_exit_node
                        })
            
            # Sort by hostname
            exit_nodes.sort(key=lambda x: x.get('hostname', ''))
            
            return exit_nodes
        except Exception:
            return []
    
    def get_current_exit_node(self):
        """Get current exit node being used"""
        try:
            status = self.get_status()
            if not status:
                return None
            
            # Check ExitNodeStatus at root level first (this is the most reliable)
            exit_node_status = status.get('ExitNodeStatus', {})
            exit_node_id = ''
            
            if exit_node_status:
                if isinstance(exit_node_status, dict):
                    # ExitNodeStatus is a dict with ID field
                    exit_node_id = exit_node_status.get('ID', '')
                elif exit_node_status:
                    # ExitNodeStatus might be just the ID string
                    exit_node_id = str(exit_node_status)
            
            # Fallback: Check root level for ExitNodeID
            if not exit_node_id:
                exit_node_id = status.get('ExitNodeID', '')
            
            # Also check Self for exit node info
            if 'Self' in status:
                self_info = status['Self']
                # ExitNodeID field might be in Self
                if not exit_node_id:
                    exit_node_id = self_info.get('ExitNodeID', '')
                
                # Also check Self.ExitNodeStatus
                if not exit_node_id:
                    self_exit_status = self_info.get('ExitNodeStatus', {})
                    if self_exit_status:
                        if isinstance(self_exit_status, dict) and 'ID' in self_exit_status:
                            exit_node_id = self_exit_status.get('ID', '')
                        elif self_exit_status:
                            exit_node_id = str(self_exit_status)
                
                if exit_node_id:
                    # Also get IP from ExitNodeStatus if available (more reliable)
                    exit_node_ip = None
                    if exit_node_status and isinstance(exit_node_status, dict):
                        tailscale_ips = exit_node_status.get('TailscaleIPs', [])
                        if tailscale_ips:
                            # IPs are in format "100.x.x.x/32", extract just the IP
                            exit_node_ip = tailscale_ips[0].split('/')[0] if isinstance(tailscale_ips[0], str) else str(tailscale_ips[0])
                    
                    # Find the device with this ID - check peers first
                    # ExitNodeStatus ID might be a StableNodeID, so we need to match by IP if ID doesn't match
                    if 'Peer' in status:
                        for peer_id, peer_info in status['Peer'].items():
                            # First try matching by ID (try both string and direct comparison)
                            peer_id_str = str(peer_id)
                            exit_node_id_str = str(exit_node_id)
                            matched = False
                            
                            if peer_id_str == exit_node_id_str or peer_id == exit_node_id:
                                matched = True
                            # Also check if peer has an ID field that matches
                            elif 'ID' in peer_info and str(peer_info.get('ID', '')) == exit_node_id_str:
                                matched = True
                            # Fallback: match by IP if we have exit_node_ip
                            elif exit_node_ip:
                                peer_ips = peer_info.get('TailscaleIPs', [])
                                for peer_ip in peer_ips:
                                    peer_ip_clean = str(peer_ip).split('/')[0] if '/' in str(peer_ip) else str(peer_ip)
                                    if peer_ip_clean == exit_node_ip:
                                        matched = True
                                        break
                            
                            if matched:
                                dns_name = peer_info.get('DNSName', '')
                                ip = exit_node_ip or (peer_info.get('TailscaleIPs', [''])[0] if peer_info.get('TailscaleIPs') else '')
                                # Handle IP format if it includes /32
                                if ip and '/' in str(ip):
                                    ip = str(ip).split('/')[0]
                                hostname = peer_info.get('HostName', '')
                                if not hostname and dns_name:
                                    hostname = dns_name.split('.')[0]
                                return {
                                    'id': str(exit_node_id),
                                    'name': dns_name,
                                    'ip': ip,
                                    'hostname': hostname
                                }
                    # Check if it's self
                    self_id = self_info.get('ID', '')
                    if str(self_id) == str(exit_node_id):
                        dns_name = self_info.get('DNSName', '')
                        ip = exit_node_ip or (self_info.get('TailscaleIPs', [''])[0] if self_info.get('TailscaleIPs') else '')
                        # Handle IP format if it includes /32
                        if ip and '/' in str(ip):
                            ip = str(ip).split('/')[0]
                        hostname = self_info.get('HostName', '')
                        if not hostname and dns_name:
                            hostname = dns_name.split('.')[0]
                        return {
                            'id': str(exit_node_id),
                            'name': dns_name,
                            'ip': ip,
                            'hostname': hostname
                        }
            
            return None
        except Exception as e:
            # Return None on any error to prevent crashes
            return None
    
    def set_exit_node(self, exit_node_name=None):
        """Set or clear exit node"""
        try:
            # Check if daemon is running
            if not self.check_daemon_running():
                return False, "Tailscale daemon is not running. Please start it with: sudo systemctl start tailscaled"
            
            if exit_node_name:
                # Set exit node
                result = subprocess.run(
                    [self.tailscale_cmd, 'set', '--exit-node', exit_node_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return True, f"Exit node set to: {exit_node_name}"
                else:
                    error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                    return False, f"Failed to set exit node: {error_msg}"
            else:
                # Clear exit node
                result = subprocess.run(
                    [self.tailscale_cmd, 'set', '--exit-node='],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return True, "Exit node cleared"
                else:
                    error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                    return False, f"Failed to clear exit node: {error_msg}"
                    
        except subprocess.TimeoutExpired:
            return False, "Operation timed out"
        except FileNotFoundError:
            return False, "Tailscale command not found. Is Tailscale installed?"
        except Exception as e:
            return False, f"Error setting exit node: {str(e)}"


class TailscaleWindow(Gtk.ApplicationWindow):
    """Main application window"""
    
    def __init__(self, app):
        super().__init__(application=app, title="Tailscale Controller")
        self.set_default_size(600, 500)
        self.controller = TailscaleController()
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        self.set_child(main_box)
        
        # Header section
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        main_box.append(header_box)
        
        # Title
        title_label = Gtk.Label(label="<big><b>Tailscale Controller</b></big>")
        title_label.set_use_markup(True)
        header_box.append(title_label)
        
        # Status section
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        status_box.set_margin_top(10)
        status_box.set_margin_bottom(10)
        header_box.append(status_box)
        
        # Status label with frame for border
        self.status_frame = Gtk.Frame()
        self.status_frame.set_margin_start(0)
        self.status_frame.set_margin_end(0)
        self.status_frame.set_margin_top(0)
        self.status_frame.set_margin_bottom(0)
        status_box.append(self.status_frame)
        
        self.status_label = Gtk.Label(label="Status: Checking...")
        self.status_label.set_margin_start(8)
        self.status_label.set_margin_end(8)
        self.status_label.set_margin_top(4)
        self.status_label.set_margin_bottom(4)
        self.status_frame.set_child(self.status_label)
        
        self.current_user_label = Gtk.Label(label="")
        status_box.append(self.current_user_label)
        
        # Account section
        account_frame = Gtk.Frame(label="Account Management")
        account_frame.set_margin_top(10)
        account_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        account_box.set_margin_start(10)
        account_box.set_margin_end(10)
        account_box.set_margin_top(10)
        account_box.set_margin_bottom(10)
        account_frame.set_child(account_box)
        main_box.append(account_frame)
        
        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        account_box.append(button_box)
        
        self.login_button = Gtk.Button(label="tailscale up")
        self.login_button.connect("clicked", self.on_login)
        button_box.append(self.login_button)
        
        self.logout_button = Gtk.Button(label="tailscale down")
        self.logout_button.connect("clicked", self.on_logout)
        button_box.append(self.logout_button)
        
        # Profiles section
        profiles_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        profiles_header.set_margin_top(10)
        account_box.append(profiles_header)
        
        profiles_label = Gtk.Label(label="<b>Switch Profile:</b>")
        profiles_label.set_use_markup(True)
        profiles_label.set_halign(Gtk.Align.START)
        profiles_label.set_hexpand(True)
        profiles_header.append(profiles_label)
        
        # Plus button to add new profile
        self.add_profile_button = Gtk.Button(label="+")
        self.add_profile_button.set_tooltip_text("Add new profile nickname")
        self.add_profile_button.connect("clicked", self.on_add_profile)
        profiles_header.append(self.add_profile_button)
        
        # Profiles container - use a flow box for wrapping
        self.profiles_flow = Gtk.FlowBox()
        self.profiles_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.profiles_flow.set_max_children_per_line(3)
        self.profiles_flow.set_margin_top(5)
        self.profiles_flow.set_margin_bottom(5)
        account_box.append(self.profiles_flow)
        
        # Exit Node section
        exit_node_frame = Gtk.Frame(label="Exit Node")
        exit_node_frame.set_margin_top(10)
        exit_node_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        exit_node_box.set_margin_start(10)
        exit_node_box.set_margin_end(10)
        exit_node_box.set_margin_top(10)
        exit_node_box.set_margin_bottom(10)
        exit_node_frame.set_child(exit_node_box)
        main_box.append(exit_node_frame)
        
        # Current exit node label
        self.current_exit_node_label = Gtk.Label(label="Current: None")
        self.current_exit_node_label.set_halign(Gtk.Align.START)
        exit_node_box.append(self.current_exit_node_label)
        
        # Exit node selection
        exit_node_select_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        exit_node_select_box.set_hexpand(True)
        exit_node_box.append(exit_node_select_box)
        
        exit_node_label = Gtk.Label(label="Select Exit Node:")
        exit_node_label.set_halign(Gtk.Align.START)
        exit_node_label.set_hexpand(False)
        exit_node_select_box.append(exit_node_label)
        
        # Dropdown for exit nodes - use a fixed width to prevent movement
        self.exit_node_combo = Gtk.ComboBoxText()
        self.exit_node_combo.set_hexpand(True)
        self.exit_node_combo.set_halign(Gtk.Align.FILL)
        self.exit_node_combo.append_text("None (Direct Connection)")
        self.exit_node_combo.set_active(0)
        self.exit_node_combo.connect("changed", self.on_exit_node_changed)
        exit_node_select_box.append(self.exit_node_combo)
        
        # Turn off exit node button
        self.turn_off_exit_node_button = Gtk.Button(label="Turn Off Exit Node")
        self.turn_off_exit_node_button.connect("clicked", self.on_turn_off_exit_node)
        self.turn_off_exit_node_button.set_sensitive(False)  # Disabled by default
        exit_node_box.append(self.turn_off_exit_node_button)
        
        # Store mapping of display text to node identifier (IP or name)
        self.exit_node_map = {}
        # Flag to prevent recursive updates when refreshing
        self._refreshing_exit_nodes = False
        
        # Devices section
        devices_frame = Gtk.Frame(label="Tailscale Devices")
        devices_frame.set_margin_top(10)
        devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        devices_box.set_margin_start(10)
        devices_box.set_margin_end(10)
        devices_box.set_margin_top(10)
        devices_box.set_margin_bottom(10)
        devices_frame.set_child(devices_box)
        main_box.append(devices_frame)
        
        # Scrolled window for device list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        devices_box.append(scrolled)
        
        # Device list
        self.device_list = Gtk.ListBox()
        self.device_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.device_list)
        
        # Version label in lower left
        version_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        version_box.set_margin_top(5)
        main_box.append(version_box)
        
        version_label = Gtk.Label(label=f"Version {__version__}")
        version_label.set_halign(Gtk.Align.START)
        version_label.set_css_classes(["dim-label"])
        version_box.append(version_label)
        
        # Initial refresh
        self.refresh_status()
        
        # Auto-refresh every 5 seconds
        GLib.timeout_add_seconds(5, self.auto_refresh)
    
    def auto_refresh(self):
        """Auto-refresh status and devices"""
        self.refresh_status()
        return True  # Continue timeout
    
    def refresh_status(self):
        """Refresh status and device list"""
        is_connected = self.controller.is_connected()
        current_user = self.controller.get_current_user()
        current_exit_node = self.controller.get_current_exit_node()
        
        if is_connected:
            status_text = "Status: Connected"
            # Add exit node info to status if using one
            if current_exit_node:
                # Use DNSName (Tailscale name) - extract device name
                exit_node_dns = current_exit_node.get('name', '')
                if exit_node_dns:
                    exit_node_name = exit_node_dns.split('.')[0]
                else:
                    exit_node_name = current_exit_node.get('hostname', 'Unknown')
                status_text += f" (Exit Node: {exit_node_name})"
            self.status_label.set_text(status_text)
            self.status_label.set_css_classes(["success"])
            # Add green border using CSS
            self.status_frame.set_css_classes(["status-connected-border"])
            # Apply green border via CSS provider
            try:
                css_provider = Gtk.CssProvider()
                css = ".status-connected-border { border: 2px solid #2ec27e; border-radius: 4px; }"
                css_provider.load_from_data(css.encode())
                display = self.get_display()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception:
                pass
            if current_user:
                self.current_user_label.set_text(f"User: {current_user}")
            else:
                self.current_user_label.set_text("User: Unknown")
            # Update button states
            self.login_button.set_label("tailscale up")
            self.login_button.set_sensitive(False)  # Already connected
            self.logout_button.set_sensitive(True)
        else:
            self.status_label.set_text("Status: Disconnected")
            self.status_label.set_css_classes(["error"])
            # Remove green border
            self.status_frame.set_css_classes([])
            self.current_user_label.set_text("User: Not logged in")
            # Update button states
            self.login_button.set_label("tailscale up")
            self.login_button.set_sensitive(True)
            self.logout_button.set_sensitive(False)  # Can't logout if not connected
        
        self.refresh_profiles()
        self.refresh_exit_nodes()
        self.refresh_devices()
    
    def refresh_profiles(self):
        """Refresh the list of saved profiles"""
        # Clear existing profiles
        while True:
            child = self.profiles_flow.get_child_at_index(0)
            if child is None:
                break
            self.profiles_flow.remove(child)
        
        # Get saved profiles from config
        profiles = self.controller.load_profiles()
        
        if not profiles:
            no_profiles_label = Gtk.Label(label="No profiles saved. Click + to add a profile nickname.")
            no_profiles_label.set_css_classes(["dim-label"])
            no_profiles_label.set_margin_top(5)
            no_profiles_label.set_margin_bottom(5)
            self.profiles_flow.append(no_profiles_label)
            return
        
        # Add profile buttons
        for nickname in profiles:
            # Create a box for the button and remove button
            profile_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            
            profile_button = Gtk.Button(label=nickname)
            profile_button.set_tooltip_text(f"Switch to: {nickname}")
            # Connect click handler - use lambda to ensure nickname is captured correctly
            profile_button.connect("clicked", lambda btn, nick=nickname: self.on_profile_clicked(btn, nick))
            profile_button.set_hexpand(True)
            profile_box.append(profile_button)
            
            # Remove button (X)
            remove_button = Gtk.Button(label="×")
            remove_button.set_tooltip_text(f"Remove {nickname}")
            remove_button.set_css_classes(["destructive-action"])
            remove_button.connect("clicked", self.on_remove_profile, nickname)
            profile_box.append(remove_button)
            
            self.profiles_flow.append(profile_box)
    
    def refresh_exit_nodes(self):
        """Refresh the exit node list and current selection"""
        # Set flag to prevent recursive updates
        self._refreshing_exit_nodes = True
        
        try:
            # Get available exit nodes
            exit_nodes = self.controller.get_available_exit_nodes()
            current_exit_node = self.controller.get_current_exit_node()
            
            # Clear existing items
            # Simple approach: try to remove items until we get an error
            # Use a counter to prevent infinite loops
            max_attempts = 50
            for _ in range(max_attempts):
                try:
                    self.exit_node_combo.remove(0)
                except (ValueError, IndexError, AttributeError, TypeError, RuntimeError):
                    # No more items to remove or error occurred
                    break
            
            # Clear the mapping
            self.exit_node_map = {}
            
            # Add "None" option
            none_text = "None (Direct Connection)"
            self.exit_node_combo.append_text(none_text)
            self.exit_node_map[none_text] = None
            
            # Add available exit nodes
            selected_index = 0  # Default to "None"
            for i, node in enumerate(exit_nodes, start=1):
                # Use DNSName (Tailscale name) as the primary display name
                # DNSName is the full Tailscale name like "device.tailXXXXX.ts.net"
                # Extract just the device name part (before the first dot)
                tailscale_name = node.get('name', '')  # This is DNSName
                if tailscale_name:
                    # Extract device name from DNS name (e.g., "device.tailXXXXX.ts.net" -> "device")
                    device_name = tailscale_name.split('.')[0]
                else:
                    device_name = node.get('hostname', 'Unknown')
                
                ip = node.get('ip', '')
                online_status = "●" if node.get('online', False) else "○"
                display_name = f"{online_status} {device_name} ({ip})"
                if node.get('is_self', False):
                    display_name += " (This Device)"
                self.exit_node_combo.append_text(display_name)
                
                # Store mapping with ID for better matching - convert ID to string for consistency
                self.exit_node_map[display_name] = {
                    'id': str(node.get('id', '')),
                    'ip': node['ip'],
                    'name': node['name'],
                    'hostname': node['hostname']
                }
                
                # Check if this is the current exit node - match by ID first, then IP, then name
                if current_exit_node:
                    current_id = str(current_exit_node.get('id', ''))
                    current_ip = current_exit_node.get('ip', '')
                    current_name = current_exit_node.get('name', '')
                    node_id = str(node.get('id', ''))
                    
                    # Match by ID (most reliable) - use string comparison
                    if current_id and node_id and current_id == node_id:
                        selected_index = i
                    # Fallback to IP match
                    elif current_ip and node['ip'] and current_ip == node['ip']:
                        selected_index = i
                    # Fallback to name match
                    elif current_name and node['name'] and current_name == node['name']:
                        selected_index = i
            
            # Set selection
            self.exit_node_combo.set_active(selected_index)
            
            # Update current exit node label with better formatting
            if current_exit_node:
                # Use DNSName (Tailscale name) - extract device name
                exit_node_dns = current_exit_node.get('name', '')
                if exit_node_dns:
                    exit_node_name = exit_node_dns.split('.')[0]
                else:
                    exit_node_name = current_exit_node.get('hostname', 'Unknown')
                exit_node_ip = current_exit_node.get('ip', '')
                self.current_exit_node_label.set_text(f"✓ Current Exit Node: {exit_node_name} ({exit_node_ip})")
                self.current_exit_node_label.set_css_classes(["success"])
            else:
                self.current_exit_node_label.set_text("Current Exit Node: None (Direct Connection)")
                self.current_exit_node_label.set_css_classes([])
            
            # Enable/disable based on connection status
            is_connected = self.controller.is_connected()
            self.exit_node_combo.set_sensitive(is_connected)
            
            # Enable/disable turn off button based on whether exit node is active
            self.turn_off_exit_node_button.set_sensitive(is_connected and current_exit_node is not None)
        finally:
            # Clear flag
            self._refreshing_exit_nodes = False
    
    def refresh_devices(self):
        """Refresh the device list"""
        # Clear existing devices
        while True:
            row = self.device_list.get_row_at_index(0)
            if row is None:
                break
            self.device_list.remove(row)
        
        if not self.controller.is_connected():
            no_devices_label = Gtk.Label(label="Not connected to Tailscale")
            no_devices_label.set_margin_top(20)
            no_devices_label.set_margin_bottom(20)
            self.device_list.append(no_devices_label)
            return
        
        devices = self.controller.get_devices()
        
        if not devices:
            no_devices_label = Gtk.Label(label="No devices found")
            no_devices_label.set_margin_top(20)
            no_devices_label.set_margin_bottom(20)
            self.device_list.append(no_devices_label)
            return
        
        for device in devices:
            row = self.create_device_row(device)
            self.device_list.append(row)
    
    def create_device_row(self, device):
        """Create a row widget for a device"""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        row.set_child(box)
        
        is_online = device.get('online', False)
        
        # Device name - make it green if online
        name_label = Gtk.Label(label=device['name'])
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        if device.get('is_self', False):
            name_label.set_text(f"{device['name']} (This Device)")
            name_label.set_css_classes(["bold"])
        # Add green styling for online devices
        if is_online:
            name_label.add_css_class("success")
        box.append(name_label)
        
        # IP address - make it selectable/copyable using Entry
        ip_entry = Gtk.Entry()
        ip_entry.set_text(device['ip'])
        ip_entry.set_editable(False)
        ip_entry.set_can_focus(True)
        ip_entry.set_width_chars(15)
        ip_entry.set_halign(Gtk.Align.START)
        # Make it look like a label but be selectable
        ip_entry.set_css_classes(["flat"])
        box.append(ip_entry)
        
        # Online status - make the dot green for online devices
        if is_online:
            # Use Pango markup to make the dot green
            status_text = '<span foreground="green">●</span> Online'
            status_label = Gtk.Label(label=status_text)
            status_label.set_use_markup(True)
            status_label.set_halign(Gtk.Align.END)
            status_label.set_css_classes(["success"])
        else:
            status_text = "○ Offline"
            status_label = Gtk.Label(label=status_text)
            status_label.set_halign(Gtk.Align.END)
            status_label.set_css_classes(["warning"])
        box.append(status_label)
        
        return row
    
    def on_login(self, button):
        """Handle login/switch account button click"""
        # Disable button during operation
        button.set_sensitive(False)
        button.set_label("Connecting...")
        
        def login_thread():
            try:
                success, message = self.controller.login()
                GLib.idle_add(self.on_login_complete, success, message, button)
            except Exception as e:
                GLib.idle_add(self.on_login_complete, False, f"Unexpected error: {str(e)}", button)
        
        threading.Thread(target=login_thread, daemon=True).start()
    
    def on_login_complete(self, success, message, button):
        """Handle login completion"""
        button.set_sensitive(True)
        if success:
            # If already connected, just show info and refresh
            if "Already connected" in message:
                self.show_info(message)
            else:
                self.show_info(message)
                # Refresh after a short delay to allow authentication
                GLib.timeout_add_seconds(2, self.refresh_status)
        else:
            self.show_error(message)
        # Refresh status to update button states
        self.refresh_status()
    
    def on_add_profile(self, button):
        """Handle add profile button click"""
        # Create dialog window
        dialog = Gtk.Window(
            title="Add Profile",
            transient_for=self,
            modal=True
        )
        dialog.set_default_size(400, 150)
        
        # Main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        dialog.set_child(main_box)
        
        # Label
        label = Gtk.Label(label="Enter profile nickname:")
        label.set_halign(Gtk.Align.START)
        main_box.append(label)
        
        # Entry field
        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g., profile1, profile2")
        main_box.append(entry)
        
        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.END)
        main_box.append(button_box)
        
        # Cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: dialog.close())
        button_box.append(cancel_button)
        
        # Add button
        add_button = Gtk.Button(label="Add")
        add_button.add_css_class("suggested-action")
        
        def on_add_clicked(btn):
            nickname = entry.get_text().strip()
            dialog.close()  # Close dialog first
            if nickname:
                if self.controller.add_profile(nickname):
                    self.show_info(f"Profile '{nickname}' added successfully")
                    self.refresh_profiles()
                else:
                    self.show_error(f"Profile '{nickname}' already exists")
            else:
                self.show_error("Please enter a profile nickname")
        
        add_button.connect("clicked", on_add_clicked)
        button_box.append(add_button)
        
        # Connect Enter key to trigger Add
        def on_entry_activate(entry):
            on_add_clicked(add_button)
        
        entry.connect("activate", on_entry_activate)
        entry.grab_focus()
        
        dialog.present()
    
    def on_remove_profile(self, button, nickname):
        """Handle remove profile button click"""
        if self.controller.remove_profile(nickname):
            self.show_info(f"Profile '{nickname}' removed")
            self.refresh_profiles()
        else:
            self.show_error(f"Failed to remove profile '{nickname}'")
    
    def on_profile_clicked(self, button, nickname):
        """Handle profile button click"""
        original_label = button.get_label()
        button.set_sensitive(False)
        button.set_label("Switching...")
        
        def switch_thread():
            try:
                success, message = self.controller.switch_to_profile(nickname)
                
                # If sudo is required, show password dialog on main thread
                if success is None and message == "sudo_required":
                    # Use GLib.idle_add to ensure we're on the main thread
                    def show_dialog():
                        try:
                            self._show_password_dialog(nickname, button, original_label)
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            # Show error in dialog
                            self.show_error(f"Error showing password dialog: {str(e)}\n\nPlease check terminal for details.")
                            button.set_sensitive(True)
                            button.set_label(original_label)
                    
                    GLib.idle_add(show_dialog, priority=GLib.PRIORITY_HIGH)
                    return
                
                # Otherwise show result
                GLib.idle_add(lambda: self.on_profile_switch_complete(success, message, button, original_label))
            except Exception as e:
                import traceback
                traceback.print_exc()
                GLib.idle_add(lambda: self.on_profile_switch_complete(False, f"Error: {str(e)}", button, original_label))
        
        threading.Thread(target=switch_thread, daemon=True).start()
    
    def _show_password_dialog(self, nickname, button, original_label):
        """Show password dialog"""
        try:
            password_dialog = Gtk.Window(transient_for=self, modal=True, title="Sudo Password")
            password_dialog.set_default_size(400, 200)
            password_dialog.set_resizable(False)
            
            main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
            main_vbox.set_margin_start(20)
            main_vbox.set_margin_end(20)
            main_vbox.set_margin_top(20)
            main_vbox.set_margin_bottom(20)
            password_dialog.set_child(main_vbox)
            
            label = Gtk.Label(label=f"Enter sudo password to switch to '{nickname}':")
            label.set_wrap(True)
            main_vbox.append(label)
            
            password_entry = Gtk.PasswordEntry()
            password_entry.set_placeholder_text("Password")
            main_vbox.append(password_entry)
            
            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            button_box.set_halign(Gtk.Align.END)
            main_vbox.append(button_box)
            
            cancel_btn = Gtk.Button(label="Cancel")
            ok_btn = Gtk.Button(label="OK")
            ok_btn.add_css_class("suggested-action")
            
            def on_cancel(btn):
                password_dialog.close()
                button.set_sensitive(True)
                button.set_label(original_label)
            
            def on_ok(btn):
                pwd = password_entry.get_text()
                password_entry.set_text("")
                password_dialog.close()
                
                if pwd:
                    def do_switch():
                        try:
                            success, message = self.controller.switch_to_profile_with_sudo(nickname, pwd)
                            del pwd
                            GLib.idle_add(lambda: self.on_profile_switch_complete(success, message, button, original_label))
                        except Exception as e:
                            GLib.idle_add(lambda: self.on_profile_switch_complete(False, f"Error: {str(e)}", button, original_label))
                    threading.Thread(target=do_switch, daemon=True).start()
                else:
                    button.set_sensitive(True)
                    button.set_label(original_label)
            
            cancel_btn.connect("clicked", on_cancel)
            ok_btn.connect("clicked", on_ok)
            password_entry.connect("activate", lambda e: on_ok(ok_btn))
            
            button_box.append(cancel_btn)
            button_box.append(ok_btn)
            
            # Make sure dialog is visible and on top
            password_dialog.set_visible(True)
            password_dialog.present()
            password_dialog.raise_()
            password_entry.grab_focus()
        except Exception as e:
            import traceback
            traceback.print_exc()
            button.set_sensitive(True)
            button.set_label(original_label)
            self.show_error(f"Error creating password dialog: {str(e)}")
    
    def prompt_sudo_password(self, nickname, button, original_label):
        """Prompt user for sudo password"""
        try:
            # Create password dialog
            dialog = Gtk.Window(
                title="Sudo Password Required",
                transient_for=self,
                modal=True
            )
            dialog.set_default_size(400, 180)
            dialog.set_resizable(False)
            
            # Main content box
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
            main_box.set_margin_start(20)
            main_box.set_margin_end(20)
            main_box.set_margin_top(20)
            main_box.set_margin_bottom(20)
            dialog.set_child(main_box)
            
            # Label
            label = Gtk.Label(label=f"Enter sudo password to switch to '{nickname}':")
            label.set_halign(Gtk.Align.START)
            label.set_wrap(True)
            main_box.append(label)
            
            # Password entry field
            password_entry = Gtk.PasswordEntry()
            password_entry.set_placeholder_text("Password")
            password_entry.set_visibility(False)
            main_box.append(password_entry)
            
            # Button box
            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            button_box.set_halign(Gtk.Align.END)
            main_box.append(button_box)
            
            # Store references for callbacks
            dialog_ref = [dialog]  # Use list to avoid closure issues
            
            def on_cancel_clicked(btn):
                dialog_ref[0].close()
                button.set_sensitive(True)
                button.set_label(original_label)
            
            # Cancel button
            cancel_button = Gtk.Button(label="Cancel")
            cancel_button.connect("clicked", on_cancel_clicked)
            button_box.append(cancel_button)
            
            # OK button
            ok_button = Gtk.Button(label="OK")
            ok_button.add_css_class("suggested-action")
            
            def on_ok_clicked(btn):
                password = password_entry.get_text()
                if not password:
                    return  # Don't proceed if password is empty
                
                dialog_ref[0].close()
                # Clear password from entry immediately
                password_entry.set_text("")
                
                # Switch in background thread
                def switch_with_password():
                    try:
                        success, message = self.controller.switch_to_profile_with_sudo(nickname, password)
                        # Clear password from memory (best effort)
                        del password
                        GLib.idle_add(lambda: self.on_profile_switch_complete(success, message, button, original_label))
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        error_msg = f"Unexpected error: {str(e)}"
                        GLib.idle_add(lambda: self.on_profile_switch_complete(False, error_msg, button, original_label))
                
                threading.Thread(target=switch_with_password, daemon=True).start()
            
            ok_button.connect("clicked", on_ok_clicked)
            button_box.append(ok_button)
            
            # Connect Enter key
            def on_entry_activate(entry):
                on_ok_clicked(ok_button)
            
            password_entry.connect("activate", on_entry_activate)
            
            # Show dialog and focus password entry
            # Make sure dialog is visible and on top
            dialog.set_visible(True)
            dialog.present()
            dialog.raise_()
            password_entry.grab_focus()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            button.set_sensitive(True)
            button.set_label(original_label)
            self.show_error(f"Error showing password dialog: {str(e)}")
    
    def on_profile_switch_complete(self, success, message, button, original_label):
        """Handle profile switch completion"""
        button.set_sensitive(True)
        button.set_label(original_label)
        if success:
            self.show_info(message)
            # Refresh after a short delay to allow switch to complete
            GLib.timeout_add_seconds(2, self.refresh_status)
        else:
            self.show_error(message)
        # Refresh status to update button states
        self.refresh_status()
    
    def on_logout(self, button):
        """Handle logout button click"""
        button.set_sensitive(False)
        
        def logout_thread():
            success, message = self.controller.logout()
            GLib.idle_add(self.on_logout_complete, success, message, button)
        
        threading.Thread(target=logout_thread, daemon=True).start()
    
    def on_logout_complete(self, success, message, button):
        """Handle logout completion"""
        button.set_sensitive(True)
        if success:
            self.show_info(message)
            self.refresh_status()
        else:
            self.show_error(message)
    
    def on_exit_node_changed(self, combo):
        """Handle exit node selection change"""
        # Prevent recursive updates during refresh
        if self._refreshing_exit_nodes or not combo.get_sensitive():
            return
        
        selected_index = combo.get_active()
        if selected_index < 0:
            return
        
        selected_text = combo.get_active_text()
        if not selected_text:
            return
        
        # Disable combo during operation
        combo.set_sensitive(False)
        
        def set_exit_node_thread():
            try:
                if selected_index == 0 or selected_text == "None (Direct Connection)":
                    # Clear exit node
                    success, message = self.controller.set_exit_node(None)
                else:
                    # Get node identifier from mapping using the selected text
                    # The text should match what we stored in the map
                    node_info = self.exit_node_map.get(selected_text)
                    if node_info:
                        # Use IP address (most reliable for tailscale set command)
                        exit_node_to_use = node_info.get('ip')
                        if not exit_node_to_use:
                            # Fallback to hostname/name
                            exit_node_to_use = node_info.get('hostname') or node_info.get('name')
                        
                        if exit_node_to_use:
                            success, message = self.controller.set_exit_node(exit_node_to_use)
                        else:
                            success, message = False, "Could not determine exit node address"
                    else:
                        # Fallback: try to extract IP from text using regex
                        import re
                        match = re.search(r'\(([0-9.]+)\)', selected_text)
                        if match:
                            exit_node_to_use = match.group(1)
                            success, message = self.controller.set_exit_node(exit_node_to_use)
                        else:
                            success, message = False, f"Could not determine exit node address for: {selected_text}"
                
                GLib.idle_add(self.on_exit_node_set_complete, success, message, combo)
            except Exception as e:
                GLib.idle_add(self.on_exit_node_set_complete, False, f"Unexpected error: {str(e)}", combo)
        
        threading.Thread(target=set_exit_node_thread, daemon=True).start()
    
    def on_exit_node_set_complete(self, success, message, combo):
        """Handle exit node set completion"""
        combo.set_sensitive(True)
        if success:
            # Refresh multiple times to ensure status is updated
            # Tailscale status might take a moment to reflect the change
            self.refresh_status()
            GLib.timeout_add_seconds(1, self.refresh_status)
            GLib.timeout_add_seconds(3, self.refresh_status)
        else:
            self.show_error(message)
            # Refresh to restore correct selection
            self.refresh_status()
    
    def on_turn_off_exit_node(self, button):
        """Handle turn off exit node button click"""
        # Disable button during operation
        button.set_sensitive(False)
        
        def clear_exit_node_thread():
            try:
                success, message = self.controller.set_exit_node(None)
                GLib.idle_add(self.on_turn_off_exit_node_complete, success, message, button)
            except Exception as e:
                GLib.idle_add(self.on_turn_off_exit_node_complete, False, f"Unexpected error: {str(e)}", button)
        
        threading.Thread(target=clear_exit_node_thread, daemon=True).start()
    
    def on_turn_off_exit_node_complete(self, success, message, button):
        """Handle turn off exit node completion"""
        button.set_sensitive(True)
        if success:
            # Refresh immediately and then again after a short delay
            self.refresh_status()
            GLib.timeout_add_seconds(1, self.refresh_status)
            GLib.timeout_add_seconds(3, self.refresh_status)
        else:
            self.show_error(message)
            # Refresh to update button state
            self.refresh_status()
    
    def show_error(self, message):
        """Show error dialog with copyable text"""
        dialog = Gtk.Dialog(
            title="Error",
            transient_for=self,
            modal=True
        )
        dialog.add_button("OK", Gtk.ResponseType.OK)
        
        # Create content area
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        dialog.set_child(content)
        
        # Error icon and label
        icon_label = Gtk.Label(label="⚠")
        icon_label.set_css_classes(["error"])
        content.append(icon_label)
        
        # Create a text view for copyable content
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(150)
        scroll.set_min_content_width(500)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.set_selectable(True)
        text_buffer = text_view.get_buffer()
        text_buffer.set_text(message)
        scroll.set_child(text_view)
        content.append(scroll)
        
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()
    
    def show_info(self, message):
        """Show info dialog with copyable text"""
        dialog = Gtk.Dialog(
            title="Information",
            transient_for=self,
            modal=True
        )
        dialog.add_button("OK", Gtk.ResponseType.OK)
        
        # Create content area
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        dialog.set_child(content)
        
        # Create a text view for copyable content
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(100)
        scroll.set_min_content_width(500)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.set_selectable(True)
        text_buffer = text_view.get_buffer()
        text_buffer.set_text(message)
        scroll.set_child(text_view)
        content.append(scroll)
        
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()


class TailscaleApp(Gtk.Application):
    """Main application"""
    
    def __init__(self):
        super().__init__(application_id="com.tailscale.gui")
        self.window = None
    
    def do_activate(self):
        """Activate the application"""
        if self.window is None:
            self.window = TailscaleWindow(self)
        self.window.present()


def main():
    """Main entry point"""
    app = TailscaleApp()
    app.run()


if __name__ == "__main__":
    main()

