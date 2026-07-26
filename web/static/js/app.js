(function () {
  const toast = document.getElementById('toast');
  let toastTimer = null;

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
  }

  document.querySelectorAll('[data-placeholder]').forEach((item) => {
    item.addEventListener('click', () => {
      showToast('Розділ «' + item.dataset.placeholder + '» ще не реалізований');
    });
  });

  const filterBtn = document.getElementById('filter-btn');
  const filterDropdown = document.getElementById('filter-dropdown');

  if (filterBtn && filterDropdown) {
    filterBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      filterDropdown.hidden = !filterDropdown.hidden;
    });

    document.addEventListener('click', (event) => {
      if (!filterDropdown.hidden && !filterDropdown.contains(event.target)) {
        filterDropdown.hidden = true;
      }
    });

    filterDropdown.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.addEventListener('change', () => {
        document
          .querySelectorAll('.action-item[data-priority="' + checkbox.value + '"]')
          .forEach((item) => {
            item.hidden = !checkbox.checked;
          });
      });
    });
  }

  const sortBtn = document.getElementById('sort-btn');
  const actionList = document.getElementById('action-list');

  if (sortBtn && actionList) {
    let byAmount = false;
    sortBtn.addEventListener('click', () => {
      byAmount = !byAmount;
      const items = Array.from(actionList.children);
      items.sort((a, b) => {
        if (byAmount) {
          return Number(b.dataset.amount || 0) - Number(a.dataset.amount || 0);
        }
        return Number(a.dataset.rank || 0) - Number(b.dataset.rank || 0);
      });
      items.forEach((item) => actionList.appendChild(item));
      sortBtn.querySelector('.sort-label').textContent = byAmount ? 'За сумою' : 'За пріоритетом';
      showToast(byAmount ? 'Відсортовано за сумою' : 'Відсортовано за пріоритетом');
    });
  }

  // Картка рекомендації: підсвічування вибраного рядка, копіювання, закриття.
  document.addEventListener('click', (event) => {
    const row = event.target.closest('.action-item');
    if (row) {
      document.querySelectorAll('.action-item.selected').forEach((item) => {
        item.classList.remove('selected');
      });
      row.classList.add('selected');
      return;
    }

    const copyBtn = event.target.closest('[data-copy-target]');
    if (copyBtn) {
      const source = document.getElementById(copyBtn.dataset.copyTarget);
      if (!source) return;
      navigator.clipboard.writeText(source.innerText.trim()).then(
        () => showToast('Чернетку скопійовано'),
        () => showToast('Не вдалося скопіювати')
      );
      return;
    }

    if (event.target.closest('#detail-close')) {
      const panel = document.getElementById('detail-panel');
      if (!panel) return;
      panel.className = 'panel detail-panel detail-empty';
      panel.innerHTML =
        '<div class="empty-icon">👈</div>' +
        '<p>Оберіть угоду зі списку зліва, щоб побачити картку рекомендації.</p>';
      document.querySelectorAll('.action-item.selected').forEach((item) => {
        item.classList.remove('selected');
      });
    }
  });
})();
