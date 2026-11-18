# Needs a person

Things that can't be done or checked from the build machines. Most important first. Sections 1, 4, 5, 6 and 7 are
also runs in [TESTING.md](TESTING.md), so a student who does that guide on Windows covers them; they are spelled
out here for you.

## 1. A real scan with a real sign-in

Everything here was tested with invented data. Nobody has yet run this version against a real Moodle and Outlook.

1. On the Releases page, download the newest "Birdbrain experimental" pre-release and unzip it into a new folder
   (not over 1.1.2).
2. Quit Birdbrain 1.1.2 if it is running (tray icon, Quit), then run the new `Birdbrain.exe`. It uses the same
   data folder, so your sign-ins and list carry over.
3. Open the menu (⋯) and choose Scan now. When the dot stops breathing, look through the list for:
   - a card with the wrong kind (a lab shown as an exam, an exam shown as homework);
   - a card on the wrong day, or showing "11:59 PM" when the real deadline has another time;
   - something missing that Moodle or your email plainly shows.
4. For a wrong kind, point at the card, press **E** and say what it is. Scan again and check it stayed.
5. Write down what was wrong, with the card's title as Birdbrain shows it (leave out anything personal).

Why it matters: the rules that replaced Jev (`birdbrain/reader.py`) were written from examples. Real course pages
will have wordings they haven't seen.

## 2. The Mac: one group of testers, one guide

Nobody has seen this app on a Mac. GitHub's Macs (macOS 15, Apple silicon and Intel) build it, and on every push
they prove: the unit tests; the packaged app's self-test (ALL PASS, including a Keychain round trip and writing the
start-at-login file); the app opened the normal way stays up with its menu bar icon; the menu has Settings… and
Quit Birdbrain; a second and third copy hand over and leave; opening it again reaches the running copy; and a real
update from an older build to the new one, which keeps the old app and opens the new one.

What those machines can't do needs a student with a Mac, and it is all in one place:
**[TESTING.md](TESTING.md)**, about 25 minutes, with a box to tick for each step. Send that file's link with the
pre-release link to two or three students with Macs (one Intel if you can find one) and ask for the filled-in
copy back. The Mac-only things it covers:

1. The first open of an unsigned app: do the steps in the guide match what their macOS shows?
2. The window: does it look right, is the text sharp, do Cmd+K, Cmd+Z, Cmd+, and Cmd+Q work?
3. The menu bar icon and its menu; closing the window and getting it back from the Dock.
4. Signing in to Moodle and Outlook, with Chrome and (on a Mac without Chrome) the browser Birdbrain downloads.
5. A scan after the lid has been closed.
6. A notification: does one appear, and what does macOS ask the first time?
7. Starting at login, after signing out and in again.
8. The Update button, from Applications.
9. Which macOS version they have. It is built to open on macOS 12 and newer; only 15 has been tried.

Not on the Mac yet, and hidden there rather than broken: the shortcut that works from anywhere, the small quick
write window, and opening a card by clicking its notification. Each needs code that can only be written with a
Mac to try it on.

## 3. The motion: yours to approve

A film of the list being used was made for you (not kept in the repository). To make it again:
`python tests/ui/preview_recording.py some-folder` (needs Playwright's Chromium and ffmpeg). It shows Glass at
night and Focus by day at Full, then motion Off.

What to decide, and where each one is changed:

1. The ripple and the sheen (Glass, Full only): too much, too little, or gone. Five numbers at the top of
   `birdbrain/feel.py`: `--ripple-size`, `--ripple-time`, `--ripple-light`, `--sheen-size`, `--sheen-light`.
   To remove either for good, make `lively()` in the same file return false, or delete its few lines.
2. How far a carried card lifts and leans: `.fly.dragging .row` and `lean` in `birdbrain/dragdrop.py`.
3. The shared timings and the spring: the first lines of `TOKENS_CSS` in `birdbrain/motion.py`.

And on a real PC, since only a headless browser has tried it:

1. Drag a card up and down its day, onto another day, and onto Completed at the bottom of the window. It should
   keep up with the mouse with no stutter.
2. Drag something due today onto tomorrow: it should shake, go back, and say why.
3. On a touch screen, press and hold a card, then drag. A quick swipe should still scroll the list.
4. Press M on a card, move it with the arrows, press Enter.

## 4. The Update button on a real PC

The build machine performs a real update from a zip (the swap, the backup and the restart), and the download from
GitHub was checked from Linux. The two have not been done together, from the button, on a student's PC.

1. Keep the build from section 1 installed until a newer pre-release appears on the Releases page.
2. Menu › Check for updates. It should say a newer build is available.
3. Press "Update to … and restart". Birdbrain should close and come back by itself within a minute or two, and
   Settings › Updates should name the new build.
4. If it doesn't come back, open `%LOCALAPPDATA%\Birdbrain-update\update.log` and send its contents.

One thing to know first: builds up to and including `exp-2.0.0-5b55b3e` picked the wrong build as the newest
(GitHub lists builds by name, not by date, and they took the first). Found in the last check and fixed. If you
or a tester still has one of those, don't use its Update button: download the newest pre-release from the
Releases page by hand once. Every build after that updates to the right one.

On a Mac the same button is run 12 of the testers' guide; its log is `~/Library/Caches/Birdbrain-update/update.log`.

## 5. Notifications on a real PC

The rules for what is said and when are tested, and the build machine checks Birdbrain can listen for a click on
its notification. Nobody has seen one or clicked one.

1. Settings › Notifications › **Show me one**. A notification should appear by the clock within a couple of
   seconds, titled like "Due tonight", with one line under it.
2. Close Birdbrain's window, press **Show me one** again first if the notification has gone, and click the
   notification. Birdbrain's window should come up with that card outlined and focused.
3. Set "In the evening" to two minutes from now with something due today on your list, and wait: one
   notification, "Due tonight: …".

Things to note if they happen: no notification at all (Windows Settings › System › Notifications may have
Birdbrain off, or Do not disturb is on); clicking it does nothing; it opens the window but not on the card.

## 6. The quick write shortcut on a real PC

The build machine checks that Windows gives Birdbrain Ctrl+Alt+Space and that pressing it opens quick write
without an error. Nobody has looked at the small window.

1. With Birdbrain running and its window closed, click into another program (a browser, say).
2. Press Ctrl+Alt+Space. A small dark line should appear on top, about a third of the way down the screen, with
   the cursor already in it.
3. Type `test from anywhere tmr 9am` and press Enter. It should say "Added …" and disappear by itself, and the
   main window should stay closed.
4. Open Birdbrain: the item should be under Tomorrow at 9:00 AM.
5. Press the shortcut again, then Esc: the line should go away.

Things to note if they happen: the line opens but typing goes to the other program (you have to click it first);
it opens behind other windows; it has a white flash or a title bar; it appears on the wrong screen.

## 7. Telegram with a real bot

Everything Birdbrain does with Telegram is tested against a stand-in. A real bot needs a Telegram account.

1. Settings › Advanced › Telegram. Follow the four steps: @BotFather, /newbot, paste the token, send the bot
   `/start` and the code. The page should move to step 4 by itself within a few seconds of sending the code.
2. Press **Send a test**. Your phone should get one line with a button under it.
3. Tap the button. If it named a real card, that card moves to Completed on the PC within a second or two.
4. Text the bot `dentist tue 3pm #appointment`. It should answer "Added: Dentist", with the day and time, and the
   card should be on the PC's list. Tap **Undo**: it goes.
5. Send `/list`.
6. Open `%APPDATA%\Birdbrain\config.json`: the token must not be in it. Control Panel › Credential Manager ›
   Windows Credentials should list `Birdbrain/telegram_token`.
7. **Turn off** (twice). The credential should be gone from Credential Manager.

## 8. Signing both apps (later, and it costs money)

Neither build is signed. Windows shows "Windows protected your PC" and macOS refuses the first open; the README
and the testers' guide give the way past both. Signing removes those warnings. It costs money and needs your legal
name, so it is yours to decide. Prices are from late 2026: check each page before paying.

### Mac: about $99 a year

What you need:

1. An Apple Account with two-factor sign-in, and the **Apple Developer Program** as an individual
   (developer.apple.com/programs/enroll, $99 a year, your legal name; approval takes a day or two).
2. A **Developer ID Application** certificate: Xcode › Settings › Accounts › Manage Certificates › + › Developer ID
   Application (or developer.apple.com › Certificates, with a request made in Keychain Access).
3. An **app-specific password** for notarising: account.apple.com › Sign-In and Security › App-Specific Passwords.
4. Your Team ID (developer.apple.com › Membership details).

On a Mac, after `python build.py` (replace the name, the team and the version):

```
ID="Developer ID Application: Your Name (TEAMID)"
cat > entitlements.plist <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>com.apple.security.cs.allow-jit</key><true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
  <key>com.apple.security.cs.disable-library-validation</key><true/>
</dict></plist>
XML
codesign --force --deep --options runtime --timestamp --entitlements entitlements.plist --sign "$ID" dist/Birdbrain.app
codesign --verify --deep --strict --verbose=2 dist/Birdbrain.app

xcrun notarytool store-credentials birdbrain --apple-id you@example.com --team-id TEAMID   # asks for the app-specific password, once
ditto -c -k --keepParent dist/Birdbrain.app dist/Birdbrain-VERSION-mac-arm64.zip
xcrun notarytool submit dist/Birdbrain-VERSION-mac-arm64.zip --keychain-profile birdbrain --wait
xcrun stapler staple dist/Birdbrain.app
ditto -c -k --keepParent dist/Birdbrain.app dist/Birdbrain-VERSION-mac-arm64.zip           # again, now with the ticket inside

# the .dmg: make it from the stapled app as build.py does, then
codesign --timestamp --sign "$ID" dist/Birdbrain-VERSION-mac-arm64.dmg
xcrun notarytool submit dist/Birdbrain-VERSION-mac-arm64.dmg --keychain-profile birdbrain --wait
xcrun stapler staple dist/Birdbrain-VERSION-mac-arm64.dmg
spctl --assess --type open --context context:primary-signature -v dist/Birdbrain-VERSION-mac-arm64.dmg   # should say "accepted"
```

If notarising is refused, `xcrun notarytool log <the id it printed> --keychain-profile birdbrain` names the file
and the reason; it is usually one binary inside the app that didn't get the hardened runtime.

To have GitHub do it on every push: export the certificate from Keychain Access as a `.p12`, and add five
repository secrets (Settings › Secrets and variables › Actions): `MAC_CERT_P12` (the file, base64), `MAC_CERT_PASSWORD`,
`APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD`. Then the place to change is one line in `build_mac` in
`build.py` (`codesign --force --deep --sign -`, where `-` means "no identity"), plus the notarising commands
above after it. Say when the secrets are there and that is an hour's work.

Signed builds also let two things be finished: notifications that come from Birdbrain by name, and an updater
that checks the new app's signature before swapping it in.

### Windows: free, about $10 a month, or about $200 to $400 a year

Three ways, cheapest first.

1. **SignPath Foundation: free for open-source projects** (signpath.org). Birdbrain qualifies on licence (MIT,
   public repository). You apply, add a short "code signing policy" page to the repository, turn on two-factor
   sign-in on GitHub, and approve each release yourself. The publisher Windows shows is "SignPath Foundation",
   not your name. Signing happens from the GitHub workflow with their action.
2. **Azure Artifact Signing** (it was called Trusted Signing; azure.microsoft.com/pricing/details/artifact-signing):
   about $10 a month for the basic plan, billed from the day the account is made. Individuals in the USA and
   Canada can sign up; Microsoft checks a government ID. Windows shows your name. It signs from the workflow with
   `azure/trusted-signing-action`, or by hand:
   ```
   signtool sign /v /fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 ^
     /dlib Azure.CodeSigning.Dlib.dll /dmdf metadata.json dist\Birdbrain\Birdbrain.exe
   ```
3. **A certificate from a certificate authority** (Sectigo, DigiCert, SSL.com, Certum): about $200 to $400 a year
   for the ordinary ("OV") kind. Since 2023 the key has to live on a USB token they post to you or in their cloud
   service, so signing on GitHub only works with the cloud kind. With the token plugged into a PC:
   ```
   signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a dist\Birdbrain\Birdbrain.exe
   signtool verify /pa /v dist\Birdbrain\Birdbrain.exe
   ```
   The dearer "EV" kind no longer skips the warning, so it isn't worth it.

Whichever you choose: sign `dist\Birdbrain\Birdbrain.exe` after PyInstaller has made it and before `build.py`
zips the folder (`signtool` comes with the Windows SDK). A new certificate still shows the SmartScreen warning for
the first few hundred downloads, until Windows has seen the app enough; after that it is gone for every build
signed the same way.

My suggestion: SignPath first, since it is free and the wait is only their review. Pay Apple when the students
with Macs say it is worth keeping.

## 9. An old TypeSafe key

If you used Jev in 1.1.2, your key is still in `%APPDATA%\Birdbrain\config.json` (as `typesafe_api_key`) until
this version next saves its settings, and in the `TYPESAFE_API_KEY` environment variable if you set one. This
version never reads either. Remove the variable yourself if you want it gone: Start › "Edit environment variables
for your account".
