"""Microsoft Store apps: which packages are offered, their names and logos, and how one is removed. Nothing is
removed: PowerShell is replaced in every test that would change something."""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import raster
import storeapps

PUBLISHER_ID = "8wekyb3d8bbwe"


def manifest(name, display, publisher="Contoso", apps=(("default", "Assets\\AppList.png"),), logo="Assets\\Store.png"):
    visuals = "".join(f'<Application Id="App{i}"><uap:VisualElements DisplayName="{display}" '
                      f'Square44x44Logo="{square}" AppListEntry="{entry}"/></Application>'
                      for i, (entry, square) in enumerate(apps))
    return (f'<?xml version="1.0" encoding="utf-8"?><Package xmlns="http://schemas.microsoft.com/appx/manifest/'
            f'foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10">'
            f'<Identity Name="{name}"/><Properties><DisplayName>{display}</DisplayName>'
            f'<PublisherDisplayName>{publisher}</PublisherDisplayName><Logo>{logo}</Logo></Properties>'
            f'<Applications>{visuals}</Applications></Package>')


class StoreAppsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="simpletool-store-test-")
        self.packages = []
        self.patches = [mock.patch.object(storeapps.engine, "other_account", lambda: None),
                        mock.patch.object(storeapps, "_packages", lambda: list(self.packages))]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def package(self, name, display="App", version="1.0.0.0", entries=(("default", "Assets\\AppList.png"),),
                write=True, **fields):
        full = f"{name}_{version}_x64__{PUBLISHER_ID}"
        location = os.path.join(self.tmp, full)
        if write:
            os.makedirs(location)
            with open(os.path.join(location, "AppxManifest.xml"), "w", encoding="utf-8") as f:
                f.write(manifest(name, display, apps=entries))
        record = {"Name": name, "PackageFullName": full, "PackageFamilyName": f"{name}_{PUBLISHER_ID}",
                  "InstallLocation": location, "Version": version, "SignatureKind": 3, "IsFramework": False,
                  "IsResourcePackage": False, "IsBundle": False, "NonRemovable": False}
        record.update(fields)
        self.packages.append(record)
        return record

    def test_only_apps_a_person_can_remove(self):
        self.package("Contoso.Notes", "Contoso Notes", "2.5.0.0")
        self.package("Fabrikam.Paint", "Paint Studio")
        self.package("Microsoft.VCLibs.140.00", IsFramework=True)
        self.package("Contoso.Notes.Resources", IsResourcePackage=True)
        self.package("Microsoft.Windows.ShellExperienceHost", NonRemovable=True)
        self.package("Contoso.SystemPart", SignatureKind=storeapps.SIGNATURE_SYSTEM)
        self.package("Microsoft.WindowsStore", "Microsoft Store")  # Windows relies on it
        self.package("Microsoft.SecHealthUI", "Windows Security")
        self.package("MicrosoftWindows.Client.CBS", "Windows Feature Experience Pack")
        self.package("Microsoft.HEVCVideoExtension", "HEVC", entries=(("none", "Assets\\AppList.png"),))  # no Start
        self.package("Contoso.Gone", write=False)  # its folder is not there
        self.package("Contoso.Odd", PackageFullName="Contoso.Odd'; Remove-Item C:\\")  # not a package name
        apps = storeapps.installed_apps()
        self.assertEqual([app.name for app in apps], ["Contoso Notes", "Paint Studio"])
        notes = apps[0]
        self.assertEqual((notes.key, notes.full_name, notes.version, notes.publisher),
                         (f"appx:Contoso.Notes_{PUBLISHER_ID}", f"Contoso.Notes_2.5.0.0_x64__{PUBLISHER_ID}", "2.5.0.0",
                          "Contoso"))
        self.assertIsNotNone(notes.installed)
        self.assertGreater(notes.size, 0, "the size of its folder")

    def test_another_account(self):
        # Get-AppxPackage lists the apps of the account SimpleTool runs as, not of the person signed in
        with mock.patch.object(storeapps.engine, "other_account", lambda: ("PC\\admin", "PC\\user")):
            self.assertIsNone(storeapps.installed_apps())

    def test_names_from_resources(self):
        self.assertEqual(storeapps.resource_uris("Contoso.Notes", "ms-resource:AppName"),
                         ["ms-resource://Contoso.Notes/Resources/AppName", "ms-resource://Contoso.Notes/AppName"])
        self.assertEqual(storeapps.resource_uris("Contoso.Notes", "ms-resource:Resources/AppName"),
                         ["ms-resource://Contoso.Notes/Resources/AppName",
                          "ms-resource://Contoso.Notes/Resources/Resources/AppName"])
        self.assertEqual(storeapps.resource_uris("Contoso.Notes", "ms-resource:/Strings/Title"),
                         ["ms-resource://Contoso.Notes/Strings/Title"])
        uri = "ms-resource://Contoso.Notes/resources/APP_NAME"
        self.assertEqual(storeapps.resource_uris("Contoso.Notes", uri), [uri])
        self.assertEqual(storeapps.resolve("full", "Contoso.Notes", " Notes "), "Notes", "plain text stays")
        # A resource Windows cannot read: the name of the app in Start, then the package name
        self.package("Contoso.Notes", "ms-resource:AppName")
        self.assertEqual([app.name for app in storeapps.installed_apps()], ["Contoso.Notes"])

    def test_resource_of_an_installed_app(self):
        # Calculator comes with Windows; if it is installed, its name is read from its resources
        calculator = [p for p in self.packages_live() if p["Name"] == "Microsoft.WindowsCalculator"]
        if not calculator:
            self.skipTest("Calculator is not installed")
        name = storeapps.resolve(calculator[0]["PackageFullName"], "Microsoft.WindowsCalculator", "ms-resource:AppName")
        self.assertTrue(name and not name.startswith("ms-resource"))

    def packages_live(self):
        for patch in reversed(self.patches):
            patch.stop()
        try:
            return storeapps._packages()
        except OSError:
            return []
        finally:
            for patch in self.patches:
                patch.start()

    def test_logo_file(self):
        assets = os.path.join(self.tmp, "Assets")
        os.makedirs(assets)
        names = ["AppList.png", "AppList.scale-100.png", "AppList.scale-200.png", "AppList.scale-400.png",
                 "AppList.targetsize-24_altform-unplated.png", "AppList.targetsize-32_altform-unplated.png",
                 "AppList.targetsize-32_altform-unplated_contrast-black.png", "AppList.targetsize-48.png",
                 "AppList.targetsize-32_altform-lightunplated.png", "AppListOther.png"]
        for name in names:
            open(os.path.join(assets, name), "wb").close()
        pick = lambda size=32: os.path.basename(storeapps.logo_file(self.tmp, "Assets\\AppList.png", size))
        self.assertEqual(pick(), "AppList.targetsize-32_altform-unplated.png")
        self.assertEqual(pick(24), "AppList.targetsize-24_altform-unplated.png")
        # Without size variants: the largest scale up to 200 %, then the file itself
        for name in names[4:9]:
            os.remove(os.path.join(assets, name))
        self.assertEqual(pick(), "AppList.scale-200.png")
        for name in names[1:4]:
            os.remove(os.path.join(assets, name))
        self.assertEqual(pick(), "AppList.png")
        self.assertIsNone(storeapps.logo_file(self.tmp, "Missing\\Logo.png"))
        self.assertIsNone(storeapps.logo_file(self.tmp, None))

    def test_logo_png(self):
        # A 64 x 48 red picture becomes a 32 x 32 PNG, centred, with see-through edges
        path = os.path.join(self.tmp, "logo.png")
        with open(path, "wb") as f:
            f.write(raster.png(64, 48, bytes([255, 0, 0, 255]) * 64 * 48))
        data = storeapps.logo_png(path, 32)
        self.assertTrue(data.startswith(b"\x89PNG"))
        self.assertEqual(int.from_bytes(data[16:20], "big"), 32)
        self.assertIsNone(storeapps.logo_png(os.path.join(self.tmp, "none.png"), 32))

    def test_remove(self):
        app = storeapps.StoreApp("Contoso.Notes", f"Contoso.Notes_2.5.0.0_x64__{PUBLISHER_ID}",
                                 f"Contoso.Notes_{PUBLISHER_ID}", "Contoso Notes")
        scripts = []
        with mock.patch.object(storeapps, "_powershell", lambda script: scripts.append(script) or (0, "", "")):
            storeapps.remove(app)
        self.assertEqual(scripts, ["[Console]::OutputEncoding = [Text.Encoding]::UTF8; "  # Windows' message in UTF-8
                                   f"Remove-AppxPackage -Package 'Contoso.Notes_2.5.0.0_x64__{PUBLISHER_ID}' "
                                   "-ErrorAction Stop"])
        with mock.patch.object(storeapps, "_powershell", lambda script: (1, "", "Deployment failed 0x80073CFA\nmore")):
            with self.assertRaisesRegex(OSError, "0x80073CFA"):
                storeapps.remove(app)
        # Never a protected package, never text that is not a package name
        with mock.patch.object(storeapps, "_powershell", lambda script: self.fail("must not run")):
            for package, full in (("Microsoft.WindowsStore", f"Microsoft.WindowsStore_1.0.0.0_x64__{PUBLISHER_ID}"),
                                  ("Contoso.Notes", "Contoso.Notes'; Remove-Item C:\\ -Recurse; '")):
                with self.assertRaises(ValueError):
                    storeapps.remove(storeapps.StoreApp(package, full, package, package))

    def test_still_installed(self):
        app = storeapps.StoreApp("Contoso.Notes", "x", f"Contoso.Notes_{PUBLISHER_ID}", "Contoso Notes")
        self.assertFalse(storeapps.still_installed(app))
        self.package("Contoso.Notes", version="2.6.0.0")  # updated meanwhile: still the same app
        self.assertTrue(storeapps.still_installed(app))

    def test_packages_output(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.patches = []
        one = {"Name": "Contoso.Notes"}
        with mock.patch.object(storeapps, "_powershell", lambda script: (0, "\ufeff" + json.dumps(one), "")):
            self.assertEqual(storeapps._packages(), [one], "a single package comes as an object")
        with mock.patch.object(storeapps, "_powershell", lambda script: (0, json.dumps([one, one]), "")):
            self.assertEqual(len(storeapps._packages()), 2)
        # One broken package makes PowerShell exit with 1, but the list it printed is whole
        with mock.patch.object(storeapps, "_powershell", lambda script: (1, json.dumps([one]), "a package is broken")):
            self.assertEqual(storeapps._packages(), [one])
        with mock.patch.object(storeapps, "_powershell", lambda script: (1, "", "Get-AppxPackage : Access denied")):
            with self.assertRaisesRegex(OSError, "Access denied"):
                storeapps._packages()

    def test_protected(self):
        for name in ("Microsoft.WindowsStore", "microsoft.desktopappinstaller", "Microsoft.UI.Xaml.2.8",
                     "Microsoft.NET.Native.Framework.2.2", "MicrosoftWindows.CrossDevice", "windows.immersivecontrolpanel",
                     "Microsoft.XboxIdentityProvider", "Microsoft.MicrosoftEdge.Stable"):
            self.assertTrue(storeapps.protected(name), name)
        for name in ("Microsoft.WindowsCalculator", "Microsoft.BingWeather", "Clipchamp.Clipchamp", "SpotifyAB.Spotify"):
            self.assertFalse(storeapps.protected(name), name)


if __name__ == "__main__":
    unittest.main()
