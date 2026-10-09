document.addEventListener('DOMContentLoaded', function() {
    const inputElem = document.getElementById('input-elem');
    const inputContainer = document.querySelector('.input-container');

    inputElem.addEventListener('input', function() {
        if (inputElem.value.length > 0) {
            inputContainer.classList.add('active');
        } else {
            inputContainer.classList.remove('active');
        }
    });
});



document.addEventListener('DOMContentLoaded', function() {
    // Находим нужные элементы
    const inputElem = document.getElementById('input-elem');
    const customCaret = document.querySelector('.caretca-custom');

    // Создаем невидимый элемент-измеритель
    const measureSpan = document.createElement('span');
    const inputStyles = window.getComputedStyle(inputElem);
    const textStyles = [
        'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'fontVariant',
        'letterSpacing', 'textTransform', 'textIndent', 'wordSpacing'
    ];
    textStyles.forEach(style => {
        measureSpan.style[style] = inputStyles[style];
    });
    measureSpan.style.whiteSpace = 'pre';
    measureSpan.style.visibility = 'hidden';
    measureSpan.style.position = 'absolute';
    measureSpan.style.top = '0';
    measureSpan.style.left = '0';
    document.body.appendChild(measureSpan);

    // Функция для обновления позиции каретки
    function updateCaretPosition() {
        const selectionStart = inputElem.selectionStart;
        const textBeforeCaret = inputElem.value.substring(0, selectionStart);

        measureSpan.textContent = textBeforeCaret;
        
        const textWidth = measureSpan.offsetWidth;
        const paddingLeft = parseFloat(inputStyles.paddingLeft); // Учитываем отступ слева

        customCaret.style.left = `${textWidth + paddingLeft}px`;
    }

    // Слушатели событий
    inputElem.addEventListener('input', updateCaretPosition);
    inputElem.addEventListener('click', updateCaretPosition);
    inputElem.addEventListener('keyup', updateCaretPosition);

    // Добавляем слушатели для изменения opacity при фокусе
    inputElem.addEventListener('focus', function() {
        customCaret.style.opacity = '1';
        updateCaretPosition(); // Обновляем позицию на случай, если фокус был потерян и возвращен
    });

    inputElem.addEventListener('blur', function() {
        customCaret.style.opacity = '0';
    });

    // Начальная установка opacity
    customCaret.style.opacity = '0';
});