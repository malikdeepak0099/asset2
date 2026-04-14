function demoLogin(event){
  event.preventDefault();
  const email = document.getElementById('loginEmail').value.trim().toLowerCase();
  const password = document.getElementById('loginPassword').value.trim();
  const note = document.getElementById('authNote');

  if(email === 'admin@assetrise.io' && password === 'admin123'){
    window.location.href = 'admin-panel.html';
    return false;
  }

  if(email === 'member@assetrise.io' && password === 'member123'){
    window.location.href = 'member-dashboard.html';
    return false;
  }

  note.textContent = 'Invalid demo credentials. Use the demo login shown below the form.';
  return false;
}

function demoRegister(event){
  event.preventDefault();
  const note = document.getElementById('registerNote');
  note.textContent = 'Frontend demo only. Connect this form to a real backend and database before launch.';
  event.target.reset();
  return false;
}

function copyReferral(){
  const input = document.getElementById('refLink');
  const note = document.getElementById('copyNote');
  input.select();
  input.setSelectionRange(0, 99999);
  document.execCommand('copy');
  note.textContent = 'Referral link copied.';
}
