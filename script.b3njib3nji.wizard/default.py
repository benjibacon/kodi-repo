import os
import json
import shutil
import zipfile
import urllib.request
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_NAME = 'b3njib3nji Setup Wizard'

BACKUP_URL = (
    'https://www.dropbox.com/scl/fi/ziv28km638ziok7pmuts8/202605071326.zip'
    '?rlkey=k3gmtbc7sodl8d5pry6vdsn3u&st=0uif0n5d&dl=1'
)

# Add-ons installed directly from zip
ZIP_ADDONS = [
    ('FenLight AM',       'plugin.video.fenlight',
     'https://fenlightanonymouse.github.io/packages/plugin.video.fenlight-2.2.04.zip'),

    ('CocoScrapers Repo', 'repository.cocoscrapers',
     'https://cocojoe2411.github.io/repository.cocoscrapers-1.0.1.zip'),

    ('MadTitan Sports',   'plugin.video.madtitansports',
     'https://magnetic.website/__zips/plugin.video.madtitansports/plugin.video.madtitansports-2.0.29.zip'),
]

# Add-ons installed via Kodi after their repo is added
REPO_ADDONS = [
    'script.module.cocoscrapers',
    'script.xbmc.backuprestore',
]

DIALOG = xbmcgui.Dialog()


# ── helpers ──────────────────────────────────────────────────────────────────

def log(msg):
    xbmc.log(f'[b3njib3nji Wizard] {msg}', xbmc.LOGINFO)


def notify(msg):
    xbmc.executebuiltin(f'Notification({ADDON_NAME},{msg},5000)')


def download(url, dest, progress, label, pct):
    progress.update(pct, f'Downloading {label}...')
    log(f'Downloading {url}')
    urllib.request.urlretrieve(url, dest)


def install_zip(name, addon_id, url, progress, pct):
    """Download a zip and extract it directly into the Kodi addons folder."""
    temp_dir  = xbmcvfs.translatePath('special://temp/')
    addons_dir = xbmcvfs.translatePath('special://home/addons/')
    zip_path  = os.path.join(temp_dir, f'{addon_id}.zip')

    try:
        download(url, zip_path, progress, name, pct)
        progress.update(pct, f'Installing {name}...')
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(addons_dir)
        log(f'{name} installed OK')
        return True
    except Exception as exc:
        log(f'ERROR installing {name}: {exc}')
        notify(f'Warning: {name} install failed — check logs')
        return False
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)


def restore_backup(progress, pct):
    """Download the Dropbox backup and restore addon_data to Kodi userdata."""
    temp_dir    = xbmcvfs.translatePath('special://temp/')
    userdata_dir = xbmcvfs.translatePath('special://home/userdata/')
    backup_zip  = os.path.join(temp_dir, 'b3njib3nji_backup.zip')
    extract_dir = os.path.join(temp_dir, 'b3njib3nji_backup_extracted')

    try:
        download(BACKUP_URL, backup_zip, progress, 'your settings', pct)
        progress.update(pct, 'Restoring your configuration...')

        # Extract to a temp folder first so we can inspect the structure
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        with zipfile.ZipFile(backup_zip, 'r') as z:
            z.extractall(extract_dir)

        # Handle both backup structures:
        #   Structure A: addon_data/ at root  → maps to special://home/userdata/
        #   Structure B: userdata/addon_data/ at root → maps to special://home/
        addon_data_direct = os.path.join(extract_dir, 'addon_data')
        addon_data_nested = os.path.join(extract_dir, 'userdata', 'addon_data')

        if os.path.isdir(addon_data_direct):
            src = extract_dir
        elif os.path.isdir(addon_data_nested):
            src = os.path.join(extract_dir, 'userdata')
        else:
            # Fall back: extract everything to userdata and hope for the best
            src = extract_dir

        # Copy everything from src into userdata (merge, don't overwrite add-ons)
        for item in os.listdir(src):
            if item.lower() == 'addons':
                continue  # skip add-on code — we install fresh from source
            s = os.path.join(src, item)
            d = os.path.join(userdata_dir, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        log('Backup restored OK')
        return True

    except Exception as exc:
        log(f'ERROR restoring backup: {exc}')
        notify('Warning: settings restore failed — you may need to configure manually')
        return False
    finally:
        for path in (backup_zip, extract_dir):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
            except Exception:
                pass


def set_rd_token(token):
    """Write the Real-Debrid token into FenLight AM's settings."""
    try:
        addon = xbmcaddon.Addon('plugin.video.fenlight')
        # Try the most common setting IDs used by FenLight variants
        for setting_id in ('rd_token', 'providers.realdebrid.token', 'realdebrid_token'):
            try:
                addon.setSetting(setting_id, token)
                log(f'RD token saved to setting: {setting_id}')
                return True
            except Exception:
                continue
    except Exception as exc:
        log(f'Could not save RD token automatically: {exc}')
    return False


# ── main wizard ───────────────────────────────────────────────────────────────

def run():
    # ── welcome ──
    if not DIALOG.yesno(
        ADDON_NAME,
        ('Welcome!\n\n'
         'This wizard will automatically:\n'
         '  • Install FenLight AM, CocoScrapers, MadTitan Sports & Backup\n'
         '  • Restore your pre-configured Kodi settings\n'
         '  • Ask for your Real-Debrid API key\n\n'
         'Have your [B]Real-Debrid API key[/B] ready.\n\n'
         'Continue?'),
    ):
        return

    total = len(ZIP_ADDONS) + 3  # zips + repo refresh + backup + credentials
    step  = 0

    progress = xbmcgui.DialogProgress()
    progress.create(ADDON_NAME, 'Starting...')

    # ── install add-ons from zip ──
    for name, addon_id, url in ZIP_ADDONS:
        if progress.iscanceled():
            progress.close()
            return
        pct = int(step / total * 100)
        install_zip(name, addon_id, url, progress, pct)
        step += 1

    # ── refresh repos + install repo-sourced add-ons ──
    if not progress.iscanceled():
        pct = int(step / total * 100)
        progress.update(pct, 'Refreshing repositories...')
        xbmc.executebuiltin('UpdateLocalAddons')
        xbmc.sleep(2000)
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.sleep(6000)

        for addon_id in REPO_ADDONS:
            progress.update(pct, f'Installing {addon_id}...')
            xbmc.executebuiltin(f'InstallAddon({addon_id})')
            xbmc.sleep(3000)

        step += 1

    # ── restore backup ──
    if not progress.iscanceled():
        pct = int(step / total * 100)
        restore_backup(progress, pct)
        step += 1

    # ── final addon refresh ──
    progress.update(95, 'Finishing up...')
    xbmc.executebuiltin('UpdateLocalAddons')
    xbmc.sleep(2000)

    progress.close()

    # ── Real-Debrid token ──
    rd_key = DIALOG.input(
        'Enter your Real-Debrid API Key',
        type=xbmcgui.INPUT_ALPHANUM,
    )
    if rd_key:
        saved = set_rd_token(rd_key)
        if not saved:
            DIALOG.ok(
                'Real-Debrid',
                ('Your key could not be saved automatically.\n\n'
                 'Please open [B]FenLight AM → Settings → Accounts → Real-Debrid[/B] '
                 'and paste it in manually.'),
            )

    # ── Trakt ──
    DIALOG.ok(
        'Trakt Authorization',
        ('Almost done!\n\n'
         'To link Trakt, open:\n'
         '[B]FenLight AM → Settings → Accounts → Trakt → Authorise[/B]\n\n'
         'This opens a browser — just log in and you\'re set.'),
    )

    # ── done ──
    DIALOG.ok(
        'Setup Complete!',
        ('Your Kodi is ready.\n\n'
         '[B]FenLight AM[/B] — streaming via Real-Debrid\n'
         '[B]CocoScrapers[/B] — enhanced source scraping\n'
         '[B]MadTitan Sports[/B] — live sports\n'
         '[B]Backup[/B] — settings backup to Dropbox\n\n'
         'Enjoy!'),
    )

    # ── restart ──
    if DIALOG.yesno('Restart Kodi', 'A restart is recommended. Restart now?'):
        xbmc.executebuiltin('RestartApp')


run()
