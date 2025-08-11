<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Live QR Code Detection</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #e6f2f2;
            margin: 0;
            padding: 0;
            text-align: center;
            color: #333;
        }

        header {
            background-color: #cce5e5;
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }

        header img {
            height: 50px;
        }

        nav a {
            margin: 0 15px;
            text-decoration: none;
            color: #003333;
            font-weight: bold;
            font-size: 16px;
        }

        h1, h2 {
            margin-bottom: 10px;
        }

        #default, #detected {
            margin: 40px auto;
            padding: 30px 20px;
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 0 12px rgba(0,0,0,0.1);
            max-width: 500px;
        }

        #detected h1 {
            color: #007777;
        }

        #detected img {
            margin-top: 15px;
            border: 4px solid #007777;
            border-radius: 8px;
            background-color: #ffffff;
            height: 150px;
        }

        span {
            font-weight: bold;
            color: #005555;
        }

        footer {
            margin-top: 40px;
            padding: 10px;
            font-size: 14px;
            color: #777;
        }

        @media (max-width: 600px) {
            nav a {
                display: block;
                margin: 5px 0;
            }

            header {
                flex-direction: column;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>

    <header>
        <img src="images\unand-removebg-preview.png" alt="Logo">
    </header>

    <div id="default">
        <h1>Menunggu Deteksi Kendaraan...</h1>
    </div>

    <div id="detected" style="display: none;">
        <h1>Kendaraan Terdeteksi!</h1>
        <h2>Foto Barcode di Bawah</h2>
        <p>Plat Nomor: <span id="plate"></span></p>
        <p>Waktu: <span id="waktu"></span></p>
        <img id="qrcode" src="" alt="QR Code">
    </div>

    <footer>
        &copy; 2025 Sistem Deteksi QR Code. All rights reserved.
    </footer>

    <script>
        let timeoutId = null;
        let lastShownId = null;

function showDetected(data) {
    document.getElementById('plate').innerText = data.pelat_nomor;
    document.getElementById('waktu').innerText = data.waktu_dibuat;
    document.getElementById('qrcode').src = 'data:image/png;base64,' + data.gambar_qr_base64;

    document.getElementById('default').style.display = 'none';
    document.getElementById('detected').style.display = 'block';

    lastShownId = data.kode_qrcode; // simpan ID

    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
        document.getElementById('detected').style.display = 'none';
        document.getElementById('default').style.display = 'block';
    }, 15000);
}


function fetchLatest() {
    fetch('/latest-qrcode')
        .then(res => res.json())
        .then(data => {
            if (data.found && data.data.kode_qrcode !== lastShownId) {
                showDetected(data.data);
            }
        })
        .catch(err => console.error('Fetch error:', err));
}


        // Mulai polling setiap 1 detik
        setInterval(fetchLatest, 1000);

        // Panggil sekali langsung saat halaman load
        fetchLatest();


    </script>

</body>
</html>
