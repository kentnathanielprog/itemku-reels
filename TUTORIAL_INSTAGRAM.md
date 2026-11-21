# Setup akses Instagram (Facebook Login) untuk itemku Reels

Sumber: dokumen resmi Meta (Instagram Platform: Overview, Get started with Facebook Login, Audio API; dibaca 2026-11-21).
Aplikasi hanya melayani akun milik sendiri, jadi **Standard Access** cukup (tanpa App Review / Business Verification).

## Prasyarat
- Akun Instagram **Professional** (Business/Creator): Settings > Account type and tools.
- **Halaman Facebook** itemku, terhubung ke akun Instagram itu. Akun Facebook Anda harus bisa melakukan tugas di Page tersebut.
- Akun developer di https://developers.facebook.com

## Langkah
1. Buat App baru (tipe Business), biarkan Development mode.
2. Tambah produk **Facebook Login for Business** (pengaturan default).
3. Buka **Graph API Explorer**, pilih app Anda, minta izin: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, dan `instagram_manage_insights` (yang terakhir belum diverifikasi di dokumen: cek referensi Insights). Setujui dialognya.
4. `GET /me/accounts` -> catat ID Halaman. Lalu `GET /{page-id}?fields=instagram_business_account` -> angka `instagram_business_account.id` adalah **IG_USER_ID**.
5. Tukar token jadi berumur panjang: `GET /oauth/access_token?grant_type=fb_exchange_token&client_id={app-id}&client_secret={app-secret}&fb_exchange_token={token}` (sekitar 60 hari; belum diverifikasi di dokumen). Token Page turunan dari token panjang dikabarkan tidak kedaluwarsa (belum diverifikasi).
6. Simpan sebagai **variabel lingkungan di environment cloud**: `IG_USER_ID`, `IG_ACCESS_TOKEN`. Jangan tempel ke chat, jangan commit. App secret juga rahasia.
7. Allowed domains environment: `graph.facebook.com`, `rupload.facebook.com` (unggah video bertahap), `developers.facebook.com` (membaca dokumen).

## Verifikasi (hanya baca, tanpa posting)
- `GET /me/accounts` berhasil dan menampilkan Halaman.
- `GET /ig_audio?audio_type=music&user_id={IG_USER_ID}` mengembalikan daftar lagu trending (cek juga apakah tersedia untuk akun Indonesia).
- Posting live baru setelah dry-run beres: `python3 auto/publish.py --dry-run`, lalu aktifkan `audio.enabled` di `auto/config.json` dan hapus `--dry-run` dari scheduled task.

## Prompt untuk Claude in Chrome (ekstensi di browser Anda)
> Bantu saya setup aplikasi Meta untuk Instagram API dengan Facebook Login mengikuti TUTORIAL_INSTAGRAM.md langkah 1-5. Berhenti dan minta saya sendiri mengetik setiap kata sandi, kode verifikasi, dan menyetujui dialog izin. Jangan menampilkan, menyalin ke tempat lain, atau menyimpan access token dan app secret; cukup tunjukkan ID Halaman dan IG_USER_ID. Jangan klik tombol yang mengubah akun produksi tanpa konfirmasi saya.
