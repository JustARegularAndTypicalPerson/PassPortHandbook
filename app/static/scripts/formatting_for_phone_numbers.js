document.addEventListener('DOMContentLoaded', function() {
  const phoneInput = document.getElementById('input-elem');

  phoneInput.addEventListener('input', function(e) {
    let value = e.target.value;
    // Очищаем значение от всего, кроме цифр
    let cleaned = value.replace(/\D/g, '');

    // Ограничиваем количество цифр до 11
    if (cleaned.length > 11) {
      cleaned = cleaned.substring(0, 11);
    }
    
    let formattedValue = '';

    if (cleaned.startsWith('8')) {
      formattedValue = '8';
      if (cleaned.length > 1) {
        formattedValue += ' (' + cleaned.substring(1, 4);
      }
      if (cleaned.length > 4) {
        formattedValue += ') ' + cleaned.substring(4, 7);
      }
      if (cleaned.length > 7) {
        formattedValue += '-' + cleaned.substring(7, 9);
      }
      if (cleaned.length > 9) {
        formattedValue += '-' + cleaned.substring(9, 11);
      }
    } else {
      if (cleaned.length > 0) {
        formattedValue += '+7';
      }
      if (cleaned.length > 1) {
        formattedValue += ' (' + cleaned.substring(1, 4);
      }
      if (cleaned.length > 4) {
        formattedValue += ') ' + cleaned.substring(4, 7);
      }
      if (cleaned.length > 7) {
        formattedValue += '-' + cleaned.substring(7, 9);
      }
      if (cleaned.length > 9) {
        formattedValue += '-' + cleaned.substring(9, 11);
      }
    }

    e.target.value = formattedValue;
  });

  phoneInput.value = '';
});