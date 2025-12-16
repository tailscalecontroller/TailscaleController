# Tailscale GUI Controller

A modern, user-friendly Linux GUI application for managing Tailscale connections, switching between accounts, and monitoring your Tailscale network.

If this helped you with Tailscale on Linux please donate Bitcoin here:
bc1qw4tc6jxpykj45wlsfc28ehyqf7ww254766qw3s

![Tailscale Controller](https://img.shields.io/badge/Tailscale-GUI%20Controller-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![GTK](https://img.shields.io/badge/GTK-4.0-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

<img width="786" height="812" alt="image" src="https://github.com/user-attachments/assets/d179f45c-bedc-475a-9cb5-32c20fbc7030" />


## 🚀 Features

- **🔐 Account Management**: Easily switch between different Tailscale accounts and profiles
- **📱 Device List**: View all devices in your Tailscale network with real-time status
- **📊 Status Monitoring**: Real-time connection status, current user, and exit node information
- **🔄 Auto-refresh**: Automatically updates device list every 5 seconds
- **🎯 Exit Node Control**: Select and manage Tailscale exit nodes directly from the GUI
- **💾 Profile Management**: Save and quickly switch between Tailscale profile nicknames
- **🎨 Modern UI**: Clean, intuitive GTK4 interface

## 📋 Requirements

- **OS**: Ubuntu 20.04+ or other Linux distribution with GTK4 support
- **Python**: 3.8 or higher
- **Tailscale**: Installed and configured
- **GTK4**: Development libraries installed

## 🛠️ Installation

### Quick Install (All-in-One)

Copy and paste this entire block to install everything:

```bash
# Install Tailscale (if not already installed)
curl -fsSL https://tailscale.com/install.sh | sh

# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-pip

# Clone or download this repository
git clone https://github.com/tailscalecontroller/TailscaleController.git
cd TailscaleController

# Install Python packages
pip3 install -r requirements.txt

# Make scripts executable
chmod +x tailscale_gui.py setup-permissions.sh install.sh

# Set up permissions (IMPORTANT - allows profile switching without password)
./setup-permissions.sh

# (Optional) Install desktop entry for application menu
./install.sh
```

### Step-by-Step Installation

#### 1. Install Tailscale

If you haven't already installed Tailscale:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

#### 2. Install System Dependencies

```bash
# On Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-pip
```

#### 3. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

#### 4. Make Scripts Executable

```bash
chmod +x tailscale_gui.py setup-permissions.sh install.sh
```

#### 5. Set Up Permissions (IMPORTANT)

This step allows the app to switch Tailscale profiles without entering your password each time.

**Option A: Automated Setup (Recommended)**
```bash
./setup-permissions.sh
```

**Option B: Manual Setup**

Set operator permissions:
```bash
sudo tailscale set --operator=$USER
sudo systemctl restart tailscaled
```

**Option C: Passwordless Sudo (Alternative)**

If Option B doesn't work:
```bash
echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/tailscale switch *" | sudo tee /etc/sudoers.d/tailscale-gui
sudo chmod 0440 /etc/sudoers.d/tailscale-gui
```

#### 6. (Optional) Install Desktop Entry

To add the application to your application menu:

```bash
./install.sh
```

## 🎮 Usage

### Running the Application

**Method 1: From Terminal**
```bash
python3 tailscale_gui.py
```

**Method 2: As Executable**
```bash
./tailscale_gui.py
```

**Method 3: From Application Menu**

After installing the desktop entry, search for "Tailscale Controller" in your application menu.

### First Time Setup

1. **Add Profile Nicknames**: 
   - Click the "+" button to add your Tailscale profile nicknames
   - These are the nicknames you set with `tailscale set --nickname="name"`

2. **Connect to Tailscale**:
   - Click "tailscale up" to connect
   - A browser window will open for authentication
   - Select your Tailscale account and complete authentication

3. **Switch Profiles**:
   - Click any profile nickname button to switch to that Tailscale account
   - The device list automatically updates to show devices in your current network

4. **Manage Exit Nodes**:
   - Select an exit node from the dropdown menu
   - Use "Turn Off Exit Node" to return to direct connection

## 📖 How to Use

### Main Features

- **Status Display**: The top of the window shows your current connection status, logged-in user, and active exit node (if any)

- **Account Management**:
  - **tailscale up**: Connect to Tailscale or switch accounts (opens browser for authentication)
  - **tailscale down**: Disconnect from the current Tailscale account

- **Profile Switching**:
  - Add profile nicknames using the "+" button
  - Click any profile button to switch to that account
  - Remove profiles using the "×" button

- **Exit Node Management**:
  - Select an exit node from the dropdown to route traffic through it
  - Current exit node is displayed at the top
  - Use "Turn Off Exit Node" to disable exit node routing

- **Device List**:
  - View all devices in your Tailscale network
  - See device names, IP addresses, and online/offline status
  - Your current device is marked as "(This Device)"
  - IP addresses are selectable for easy copying
  - Auto-refreshes every 5 seconds

## 🔧 Troubleshooting

### "Tailscale is not installed" Error

Make sure Tailscale is installed and the `tailscale` command is available:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### Permission Errors When Switching Profiles

Run the setup permissions script:

```bash
./setup-permissions.sh
```

Or manually:
```bash
sudo tailscale set --operator=$USER
sudo systemctl restart tailscaled
```

### GTK4 Not Found

Install GTK4 development libraries:

```bash
sudo apt-get install gir1.2-gtk-4.0
```

### App Doesn't Appear in Menu

Run the install script:

```bash
./install.sh
```

Or manually:
```bash
cp tailscale-gui.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

### Tailscale Daemon Not Running

Start the Tailscale service:

```bash
sudo systemctl start tailscaled
```

## 📝 Notes

- Profile nicknames are stored in `~/.config/tailscale-gui/profiles.json`
- Profile nicknames persist between sessions
- The app auto-refreshes device list every 5 seconds
- Version number is displayed in the lower left corner of the GUI
- Exit nodes must be enabled on the device to appear in the list

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## 📄 License

This project is provided as-is for personal and commercial use.

## 🙏 Acknowledgments

- Built with [GTK4](https://www.gtk.org/) and [PyGObject](https://pygobject.readthedocs.io/)
- Designed for [Tailscale](https://tailscale.com/)

---

**Made with ❤️ for the Tailscale community**
