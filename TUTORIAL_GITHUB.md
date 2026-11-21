# Tutorial: menjalankan sistem ini di "server GitHub" (tanpa laptop menyala)

Yang berperan sebagai server adalah **GitHub Actions**: mesin Linux milik GitHub yang menjalankan skrip kita sesuai jadwal. Laptop Anda hanya dipakai satu kali untuk menyiapkan di browser.

> **Status jujur:** kode sudah lulus uji offline (10/10), tetapi workflow GitHub, panggilan Claude API, dan posting Instagram **belum pernah dijalankan sungguhan**. Itu sebabnya tutorial ini memakai urutan uji bertahap (dry-run dulu, posting nyata belakangan). Nama menu GitHub/Meta bisa sedikit berbeda dari tulisan di sini; ikuti maksudnya.

## 0. Yang harus disiapkan (sekali)
| Akun | Untuk apa |
|---|---|
| GitHub | menjalankan jadwal + menyimpan kode dan state |
| Langganan Claude (jalur B, tanpa saldo API) | `CLAUDE_CODE_OAUTH_TOKEN` (penulis, QC, pemeriksa visual), memakai batas langganan |
| Instagram Business/Creator + Meta for Developers | posting Reels via Graph API |

## 1. Buat repo privat
1. github.com -> tombol **+** -> **New repository**.
2. Nama `itemku-reels`, pilih **Private**. **Jangan** centang README, .gitignore, atau license (repo harus kosong). **Create repository**.

## 2. Masukkan kode ke repo
Pilih satu:
- **A. Lewat sesi Claude Code cloud (paling mudah):** hubungkan GitHub di https://claude.ai/connect-github, pasang Claude GitHub App ke repo ini, lalu minta Claude mendorong kode dari sesi yang menyimpannya.
- **B. Lewat git di komputer:** ekstrak `itemku-reels.tar.gz`, lalu di foldernya jalankan `git init -b main && git add -A && git commit -m "Initial import"`, kemudian ikuti perintah "push an existing repository" yang ditampilkan GitHub.
- **C. Lewat unggah web (cadangan):** "uploading an existing file" menerima seret-dan-lepas. **Awas:** folder berawalan titik (`.github`, `.claude`) sering tidak ikut terseret di Finder/Explorer. Cek setelah mengunggah bahwa `.github/workflows/produce.yml` dan `publish.yml` ada. Kalau tidak, buat lewat **Add file -> Create new file** dengan mengetik nama `.github/workflows/produce.yml` lalu tempel isinya.

Cek akhir: di halaman repo harus terlihat folder `.github`, `auto`, `short`, `scripts`, `tests`, serta berkas `CLAUDE.md`.

## 3. Aktifkan Actions dan izin tulis
1. Repo -> **Settings** -> **Actions** -> **General**.
2. **Actions permissions:** *Allow all actions and reusable workflows* (workflow kita memakai aksi resmi `actions/*`).
3. **Workflow permissions:** pilih **Read and write permissions** (dibutuhkan agar workflow bisa menyimpan state ke repo). **Save**.

## 4. Buat kunci dan simpan sebagai Secrets
**Anthropic:** console.anthropic.com -> **API Keys** -> **Create Key** -> salin (hanya tampil sekali). Di **Billing** isi saldo dan **atur batas pengeluaran bulanan** (misalnya US$20) supaya tidak ada kejutan.

**GitHub:** repo -> **Settings** -> **Secrets and variables** -> **Actions**.
- Tab **Secrets** -> **New repository secret**, tiga kali:
  - `CLAUDE_CODE_OAUTH_TOKEN` = token dari perintah `claude setup-token` (jalankan sekali di terminal yang ada Claude Code; login dengan akun langganan Anda, salin token, tempel hanya di kolom secret GitHub, jangan di chat)
  - `IG_USER_ID` = ID akun Instagram profesional (dari langkah 5)
  - `IG_ACCESS_TOKEN` = token jangka panjang (dari langkah 5)
- Tab **Variables** (opsional): `GRAPH_HOST` (`graph.instagram.com` atau `graph.facebook.com`), `GRAPH_VERSION` (mis. `v21.0`, cek yang terbaru di dokumentasi Meta), dan **`STOP`** (isi `1` kapan saja untuk menghentikan semua posting; hapus/kosongkan untuk melanjutkan).

Jangan menempel kunci di chat, issue, atau berkas repo.

## 5. Aplikasi Meta (Instagram Graph API)
Ringkas (detail dan peringatan ada di `SETUP.md`, bagian 4):
1. Akun Instagram harus **Business atau Creator**. Pilih jalur: *Instagram API with Instagram Login* (tanpa Facebook Page) atau Facebook Login (butuh Page).
2. developers.facebook.com -> **Create app** -> tambahkan produk Instagram -> beri akun Anda peran di aplikasi.
3. Minta izin publikasi konten dan insights, lalu hasilkan **token jangka panjang** dan catat **IG user id**.
4. Token berumur sekitar 60 hari: **pasang pengingat perpanjangan** (perpanjangan otomatis belum dibangun).

## 6. Uji bertahap (jangan lompat)
Semua dari repo -> tab **Actions**. Pilih workflow di kiri -> **Run workflow** (kanan) -> isi pilihan -> hijau **Run workflow**. Klik run yang berjalan untuk membaca log.

1. **produce, dry-run:** centang `dry_run`. Langkah "Offline self-test" harus hijau (itu menguji pipeline tanpa API). Log menampilkan berita terpilih dan perkiraan biaya. Belum ada panggilan API.
2. **produce, sungguhan:** jangan centang `dry_run`. Cari di log baris `LULUS`, `== selesai: X/3`, dan kalau ada `[visual]`. Di bagian bawah halaman run ada **Artifacts** `videos-<angka>`: unduh dan **tonton ketiga video** sebelum lanjut. Cek juga bahwa commit "state: produce ..." muncul di repo.
3. **publish, dry-run:** `dry_run` tercentang, `force` tercentang. Log harus memperlihatkan panggilan Graph API yang *akan* dikirim (tanpa mengirim apa pun).
4. **Satu posting nyata di akun uji:** pakai akun Instagram uji lebih dulu. Jalankan **publish** dengan `dry_run` dimatikan dan `force` dicentang. Buka Instagram dan pastikan Reel muncul dengan caption benar. **Postingan tidak bisa dihapus lewat API**, jadi jangan uji di akun utama.
5. Baru setelah itu pindahkan secrets ke akun utama.

## 7. Jadwal (sudah ada di berkas workflow)
| Workflow | Jam WIB | Cron (UTC) |
|---|---|---|
| produce | 05.27 | `27 22 * * *` |
| publish | 07.33, 12.07, 17.03 | `33 0`, `7 5`, `3 10` |

Jadwal aktif otomatis begitu berkas ada di cabang `main`. GitHub bisa menunda eksekusi beberapa menit saat sibuk; publisher selalu mengambil antrean paling lama yang jatuh tempo, jadi eksekusi yang terlewat dikejar eksekusi berikutnya.

Menghentikan: variabel repo `STOP=1` (menghentikan posting), atau **Actions -> workflow -> ... -> Disable workflow** (menghentikan semuanya).

## 8. Pemantauan tanpa laptop
- **Email gagal:** foto profil -> **Settings** -> **Notifications** -> **Actions** -> aktifkan notifikasi email untuk workflow yang gagal.
- Cek mingguan: tab **Actions** (semua hijau?), folder `auto/state/` (antrean dan `llm_usage.jsonl`), dan biaya di Console Anthropic.
- Dari Claude Code: perintah `/status` meringkas antrean, run terakhir, dan biaya.

## 9. Perkiraan biaya
- **GitHub:** sekitar 300 menit Actions per bulan (produce 6-8 menit/hari, publish sekitar 1 menit per eksekusi). Repo privat paket gratis mendapat kuota menit bulanan (sekitar 2.000; cek di Settings -> Billing akun Anda).
- **Anthropic API:** sekitar US$0,1-0,4 per hari tergantung model dan token berpikir (ukur di minggu pertama).

## 10. Masalah umum
| Gejala | Penyebab / solusi |
|---|---|
| Workflow tidak muncul di tab Actions | Folder `.github/workflows` tidak terunggah (lihat langkah 2C), atau Actions dinonaktifkan di Settings |
| Jadwal tidak berjalan | Berkas harus ada di cabang utama; cek workflow tidak dalam status Disabled |
| `git push` ditolak di langkah "Commit state" | Workflow permissions belum *Read and write* (langkah 3) |
| `CLAUDE_CODE_OAUTH_TOKEN belum diisi` | Nama secret salah ketik, atau secret dibuat di *Environment*, bukan *Repository secrets* |
| Banyak berita "gagal ambil artikel" | Sebagian situs memblokir IP data center; sistem melewatinya dan memakai kandidat lain |
| publish: "Tidak ada video jatuh tempo" | Slot belum tiba atau antrean kosong; untuk uji manual centang `force` |
| publish: video tidak ditemukan | Artifact hanya disimpan 5 hari, atau produce gagal; jalankan produce lagi |
| Instagram menolak posting | Token kedaluwarsa/izin kurang; baca pesan HTTP di log; cek dokumentasi Reels Meta |
| Mulai gagal setelah sekitar 2 bulan | Token Instagram kedaluwarsa: perpanjang |

## 11. Daftar periksa go-live
- [ ] Repo privat berisi `.github/workflows/*.yml`
- [ ] Actions aktif, izin *Read and write*
- [ ] 3 secrets terisi, batas pengeluaran Anthropic diatur
- [ ] produce dry-run dan sungguhan hijau, 3 video sudah ditonton
- [ ] publish dry-run benar, satu posting nyata di akun uji OK
- [ ] Email notifikasi gagal aktif
- [ ] Pengingat perpanjang token (tiap sekitar 50 hari)
- [ ] Tombol darurat (`STOP=1`) sudah dicoba
