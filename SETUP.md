# Tailscale GUI - Setup Guide

Complete setup instructions for installing and configuring Tailscale GUI on a new computer.

## Quick Setup (Copy & Paste All Commands)

### Step 1: Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### Step 2: Install Python Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-pip
```

### Step 3: Install Python Package Dependencies

```bash
cd ~/tailscale-gui
pip3 install -r requirements.txt
```

### Step 4: Make Scripts Executable

```bash
cd ~/tailscale-gui
chmod +x tailscale_gui.py
chmod +x setup-permissions.sh
chmod +x install.sh
```

### Step 5: Set Up Permissions (IMPORTANT - Run Once)

This allows the app to switch Tailscale profiles without entering your password each time.

**Option A: Automated Setup (Recommended)**

```bash
cd ~/tailscale-gui
./setup-permissions.sh
```

**Option B: Manual Setup**

Set operator permissions (allows tailscale commands without sudo):

```bash
sudo tailscale set --operator=$USER
sudo systemctl restart tailscaled
```

**Option C: Passwordless Sudo (Alternative)**

If Option B doesn't work, set up passwordless sudo for tailscale switch:

```bash
echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/tailscale switch *" | sudo tee /etc/sudoers.d/tailscale-gui
sudo chmod 0440 /etc/sudoers.d/tailscale-gui
```

### Step 6: (Optional) Install Desktop Entry

To add the application to your application menu:

```bash
cd ~/tailscale-gui
./install.sh
```

Or manually:

```bash
cp ~/tailscale-gui/tailscale-gui.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

## Running the Application

### Method 1: Run directly

```bash
cd ~/tailscale-gui
python3 tailscale_gui.py
```

### Method 2: Run as executable

```bash
cd ~/tailscale-gui
./tailscale_gui.py
```

### Method 3: From application menu

After installing the desktop entry, search for "Tailscale Controller" in your application menu.

## First Time Setup

1. **Add Profile Nicknames**: Click the "+" button to add your Tailscale profile nicknames
2. **Switch Profiles**: Click any nickname button to switch to that Tailscale account
3. **View Devices**: The device list automatically shows all devices in your current Tailscale network

## Troubleshooting

### "Tailscale is not installed" Error

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### "Permission denied" when switching profiles

Run the setup permissions script:

```bash
cd ~/tailscale-gui
./setup-permissions.sh
```

### GTK4 Not Found

```bash
sudo apt-get install gir1.2-gtk-4.0
```

### App doesn't appear in menu

```bash
cd ~/tailscale-gui
./install.sh
```

Or manually:

```bash
cp ~/tailscale-gui/tailscale-gui.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

## Complete Installation Script (All-in-One)

Copy and paste this entire block to install everything at once:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Install dependencies
sudo apt-get update
sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-pip

# Navigate to app directory (adjust path if needed)
cd ~/tailscale-gui

# Install Python packages
pip3 install -r requirements.txt

# Make scripts executable
chmod +x tailscale_gui.py setup-permissions.sh install.sh

# Set up permissions
./setup-permissions.sh

# Install desktop entry (optional)
./install.sh
```

## Notes

- The app stores profile nicknames in `~/.config/tailscale-gui/profiles.json`
- Profile nicknames are saved between sessions
- The app auto-refreshes device list every 5 seconds
- Version number is displayed in the lower left corner of the GUI

## Support

If you encounter issues:
1. Check that Tailscale is installed and running: `tailscale status`
2. Verify permissions are set: `tailscale switch --list` (should work without sudo)
3. Check Python dependencies: `python3 -c "import gi; gi.require_version('Gtk', '4.0')"`

