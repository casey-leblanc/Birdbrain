# Needs a person

Things that can't be done or checked from the build machines. Most important first.

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
4. For a wrong kind, point at the card, press **?** and say what it is. Scan again and check it stayed.
5. Write down what was wrong, with the card's title as Birdbrain shows it (leave out anything personal).

Why it matters: the rules that replaced Jev (`birdbrain/reader.py`) were written from examples. Real course pages
will have wordings they haven't seen.

## 2. The Update button on a real PC

The build machine performs a real update from a zip (the swap, the backup and the restart), and the download from
GitHub was checked from Linux. The two have not been done together, from the button, on a student's PC.

1. Keep the build from step 1 installed until a newer pre-release appears on the Releases page.
2. Menu › Check for updates. It should say a newer build is available.
3. Press "Update to … and restart". Birdbrain should close and come back by itself within a minute or two, and
   Settings › App › Updates should name the new build.
4. If it doesn't come back, open `%LOCALAPPDATA%\Birdbrain-update\update.log` and send its contents.

## 3. An old TypeSafe key

If you used Jev in 1.1.2, your key is still in `%APPDATA%\Birdbrain\config.json` (as `typesafe_api_key`) until
this version next saves its settings, and in the `TYPESAFE_API_KEY` environment variable if you set one. This
version never reads either. Remove the variable yourself if you want it gone: Start › "Edit environment variables
for your account".

## 4. Signing (later, the owner's call)

The app is unsigned, so Windows shows "Windows protected your PC" on first run, and the README tells students to
choose More info › Run anyway. Signing removes that. It needs a code-signing certificate in the owner's name;
project 5 lists the exact options and commands for Windows and Mac together.
