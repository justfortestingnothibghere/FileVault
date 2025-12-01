function loadDemo() {
  document.querySelector('[name="url"]').value = 'https://filevault-61ij.onrender.com';
}

setInterval(() => {
  fetch('/api/stats')
    .then(r => r.json())
    .then(d => {
      document.getElementById('total').textContent = d.total;
      document.getElementById('active').textContent = d.active;
      document.getElementById('failed').textContent = d.failed;
    });
}, 5000);
