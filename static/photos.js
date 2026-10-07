(() => {
  const status = document.getElementById('upload-status');
  const upload = document.getElementById('photo-upload');
  const input = document.getElementById('photos-input');
  const kind = document.getElementById('kind');
  const selected = document.getElementById('selected-photos');
  let urls = [];
  const announce = message => { status.textContent = message; };
  function preview() {
    urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
    selected.replaceChildren();
    const files = [...input.files];
    files.forEach((file, index) => {
      const figure = document.createElement('figure');
      const img = document.createElement('img');
      const url = URL.createObjectURL(file); urls.push(url);
      img.src = url; img.alt = 'Selected photo: ' + file.name;
      const caption = document.createElement('figcaption'); caption.textContent = 'Selected · not uploaded';
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'text-button';
      remove.textContent = 'Remove selection';
      remove.addEventListener('click', () => {
        const transfer = new DataTransfer();
        [...input.files].filter((_, i) => i !== index).forEach(f => transfer.items.add(f));
        input.files = transfer.files; preview();
      });
      figure.append(img, caption, remove); selected.append(figure);
    });
    announce(files.length ? 'Photos selected. Click Upload photos to save them.' : 'Choose photos to upload.');
  }
  input.addEventListener('change', preview);
  kind.addEventListener('change', () => { input.multiple = kind.value === 'recent'; });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (!form.matches('.photo-action')) return;
    event.preventDefault();
    if (form.matches('.remove-photo') && !confirm('Remove this saved photo?')) return;
    const data = new FormData(form);
    const files = data.getAll('photos').filter(f => f instanceof File && f.size);
    const max = data.get('replace_id') || data.get('kind') === 'childhood' ? 1 : 5;
    if (files.length > max || files.some(f => f.size > 10 * 1024 * 1024)) {
      announce(`Choose up to ${max} photo${max === 1 ? '' : 's'}, each 10 MB or smaller.`); return;
    }
    const buttons = [...document.querySelectorAll('.photo-action button')];
    buttons.forEach(button => { button.disabled = true; });
    announce(form.matches('.remove-photo') ? 'Removing photo…' : 'Uploading photos… Keep this page open.');
    try {
      const response = await fetch(form.action, { method: 'POST', body: data, headers: { Accept: 'application/json' } });
      if (response.redirected && new URL(response.url).pathname === '/login') throw new Error('Your session expired. Save a copy of any unsaved answers, then sign in again.');
      const type = response.headers.get('Content-Type') || '';
      if (!type.includes('application/json')) throw new Error('The upload could not be confirmed. Refresh to check your saved photos before trying again.');
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.message || 'The photo could not be saved. Please try again.');
      document.getElementById('saved-photos').innerHTML = result.gallery;
      if (form === upload) { input.value = ''; document.getElementById('caption').value = ''; preview(); }
      announce(result.message);
    } catch (error) {
      announce(error.message === 'Failed to fetch' ? 'Connection interrupted. Your upload may have completed; refresh to check before trying again.' : error.message);
    } finally { buttons.forEach(button => { button.disabled = false; }); }
  });
})();
