document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.media-main-choice input[data-asset-checkbox]').forEach((radio) => {
    const checkbox = document.getElementById(radio.dataset.assetCheckbox);
    if (!checkbox) return;
    checkbox.addEventListener('change', () => {
      radio.disabled = !checkbox.checked;
      if (!checkbox.checked && radio.checked) {
        radio.checked = false;
        document.getElementById('main-auto').checked = true;
      }
    });
  });
});
