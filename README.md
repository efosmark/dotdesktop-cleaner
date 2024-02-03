
# Clean up `.desktop` files

Run `python cleanup.py` in order to search through common locations for
`.desktop` files. 

 - For each file that may be erroneous, you will be prompted to either delete, edit, or ignore. If you don't have permission to edit or delete, `pkexec` will be used.

 - The editor used is defined by the `EDITOR` environment variable. To override, set it during runtime:
   
   ```shell
   EDITOR=your-favorite-editor python cleanup.py
   ```

 - This does not yet validate whether an app is installed in a flatpak, but simply that flatpak itself is installed. This is due to the executable in the `.desktop` file literally being `flatpak`.

## Resources

 - [Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry-spec/desktop-entry-spec-latest.html)
 - [Howto desktop files](https://freedesktop.org/wiki/Howto_desktop_files/)
 - [Desktop entries - ArchWiki](https://wiki.archlinux.org/title/desktop_entries)
 - [Guide to Desktop Entry Files in Linux](https://www.baeldung.com/linux/desktop-entry-files)