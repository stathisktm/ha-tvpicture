# TV Picture Mode (tvpicture)

Διαβάζει και αλλάζει το **mode εικόνας** (Έξυπνο, Δυναμική, Τυπική, Σπορ, Ταινία) σε TCL Google TV από το Home Assistant, **με μία εντολή**, χωρίς πατήματα πλήκτρων στο μενού και χωρίς root.

*Reads and sets the Picture Mode of a TCL Google TV from Home Assistant in a single adb call. Exposes a sensor and a select entity, and learns changes made with the physical remote too.*

## Πώς δουλεύει
- **Αλλαγή:** χρησιμοποιεί τη «φωνητική» είσοδο των ρυθμίσεων της TCL (`ShowWindowService`, `ITEM=picture_mode`, `MOTION=SET`). Οι ρυθμίσεις ορίζουν το mode κατευθείαν και ένα μικρό παράθυρο επιβεβαίωσης κλείνει μετά από 0,3 s. Η απευθείας υπηρεσία `tcl_tv_display` μπλοκάρεται από το SELinux για adb/εφαρμογές, γι' αυτό περνάμε από τις ρυθμίσεις.
- **Ανάγνωση:** μια μόνιμη σύνδεση `logcat` πιάνει κάθε αλλαγή, και από το τηλεχειριστήριο.

## Εγκατάσταση (HACS)
1. **HACS → ⋮ → Custom repositories** → `https://github.com/stathisktm/ha-tvpicture`, τύπος **Integration**.
2. **TV Picture Mode** → **Download** → επανεκκίνηση Home Assistant.
3. **Ρυθμίσεις → Συσκευές & υπηρεσίες → Προσθήκη → TV Picture Mode**: διάλεξε το media_player της TV και γράψε την IP της.

Χρειάζεται το ενσωματωμένο integration **Android TV** (`androidtv`) ήδη ρυθμισμένο. Χρησιμοποιείται το ίδιο κλειδί ADB, οπότε δεν ζητάει νέα έγκριση στην TV.

## Χρήση
```yaml
action: tvpicture.set_mode
target:
  entity_id: media_player.tv_adb
data:
  mode: movie   # vivid | standard | sport | movie | smart
```
Ή από την οντότητα `select` της συσκευής. `tvpicture.refresh` διαβάζει το τρέχον mode χωρίς να αλλάξει τίποτα.

## Γλώσσα TV
Η εντολή ταιριάζει με τα ονόματα **όπως φαίνονται στην οθόνη**. Είναι ρυθμισμένα για ελληνικά (`LABEL_BY_MODE` στο `const.py`). Αν η TV είναι σε άλλη γλώσσα, άλλαξέ τα εκεί.

Δοκιμασμένο σε TCL Google TV (Android 12, TvSettings 3.30.02).

## Άδεια
[MIT](LICENSE)
