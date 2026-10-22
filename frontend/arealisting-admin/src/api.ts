export async function postAction<T>(payload: object): Promise<T> {
  const csrf = (document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement | null)?.value;
  let response: Response;
  try {
    response = await fetch(window.location.href, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf || '' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error('Нет ответа от сервера. Проверьте соединение и повторите попытку.');
  }
  let result: Record<string, unknown> = {};
  try { result = await response.json(); } catch { /* An HTML error page is possible. */ }
  if (!response.ok) throw new Error(typeof result.error === 'string' ? result.error
    : 'Не удалось выполнить действие. Обновите страницу и повторите попытку.');
  return result as T;
}
