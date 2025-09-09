// Enhancements for PWA environment
// Intercepts PDF download links so the app doesn't navigate away
// and triggers a direct download instead. This avoids trapping users
// on a PDF page without navigation.

document.addEventListener('DOMContentLoaded', function () {
    if (!window.matchMedia('(display-mode: standalone)').matches) {
        return; // Not running as installed PWA
    }

    document.querySelectorAll('a[download]').forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            fetch(link.href).then(function (res) {
                const disposition = res.headers.get('Content-Disposition');
                let filename = 'report.pdf';
                if (disposition && disposition.includes('filename=')) {
                    const match = disposition.match(/filename="?([^";]+)"?/);
                    if (match && match[1]) {
                        filename = match[1];
                    }
                }
                return res.blob().then(function (blob) {
                    return { blob: blob, filename: filename };
                });
            }).then(function (data) {
                const url = URL.createObjectURL(data.blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
            }).catch(function (err) {
                console.error('PWA PDF download failed', err);
            });
        });
    });
});
