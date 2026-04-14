
const menuToggle = document.getElementById('menuToggle');
const mainNav = document.getElementById('mainNav');

if (menuToggle && mainNav) {
  menuToggle.addEventListener('click', () => {
    mainNav.classList.toggle('open');
  });
}

function handleSubmit(event) {
  event.preventDefault();
  const note = document.getElementById('formNote');
  if (note) {
    note.textContent = 'Demo form active. Connect this to email, WhatsApp, or a CRM before launch.';
  }
  event.target.reset();
  return false;
}
