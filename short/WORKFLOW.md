# Alur 1 video (hemat waktu & token)

```bash
cd /home/user/itemku-news/short
python3 make_video.py find mlbb 8                      # 1. cari berita (mlbb | roblox | gta | general), tanpa web-search
python3 make_video.py new "<url>" nama mlbb            # 2. ambil fakta + gambar -> stories/nama.json (draft)
#   3. isi hook / message / gong / credit di stories/nama.json   (hanya ini yang ditulis manual)
python3 make_video.py build stories/nama.json          # 4. lint -> render -> QA -> caption.txt
```
Batch: `python3 make_video.py build stories/a.json stories/b.json stories/c.json` (satu sesi, 3-5 video).
Opsi: `--sheet` membuat contact sheet (hanya dibuka kalau QA memberi peringatan).

## Aturan teks (dicek otomatis oleh lint)
- Santai tapi tetap bahasa Indonesia (tanpa campur Inggris berlebihan): pakai gimana, udah, nggak, banget; fakta tetap akurat.
- Di slide CTA tulis "Itemku" (hanya huruf depan kapital), ukuran huruf sama dengan teks lain.
- Santai, kapital di awal saja (jangan KAPITAL SEMUA). Maks 3 baris, ±26 huruf per baris.
- Hook: ada janji ("tunggu angkanya"). Gong: sorot `[[angka]]` (menghitung naik) atau `((kata kunci))`.
- Klaim "rekor/terbesar" wajib dengan penahan: estimasi / tercatat / menurut / data.
- Gambar per caption: `{"text":"...","img":[0,2]}` (indeks di "images"). Gambar yang dipakai ulang otomatis beda crop.
- Suara: tidak ada efek suara sama sekali (senyap). Musik: `"audio":"music/x.mp3"` atau `"music"`; efek lengkap: `"audio":"sfx","sfx_full":true`.
- Tulisan sumber di slide CTA otomatis tanpa tanggal.

## Hemat token
- Satu sesi baru per hari/batch; jangan lanjutkan percakapan panjang.
- Jangan buka gambar hasil render; QA otomatis mencetak OK / daftar masalah.
- Fakta WAJIB dicek ke isi artikel (output `new` sudah memuat ringkasan teks).
