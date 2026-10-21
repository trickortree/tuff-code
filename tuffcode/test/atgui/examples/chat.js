// Drives examples/chat.tuf: type and send a message, wait for the reply, switch chats, then screenshot.
const box = T.q('.at-textarea');
const before = T.qa('.at-scroll .at-text').length;
T.type(box, 'Can we ship it today?');
T.key('Enter', {}, box);
const sent = await T.until(() => T.qa('.at-text').some((e) => e.textContent === 'Can we ship it today?'));
const typingShown = await T.until(() => { const s = T.q('.at-spinner'); return s && s.style.display !== 'none'; });
await T.shot('chat-typing');
const replied = await T.until(() => T.qa('.at-scroll .at-text').length === before + 2 && T.q('.at-spinner').style.display === 'none', 5000);
await T.wait(350);
await T.shot('chat');
T.done({ sent: !!sent, typingShown: !!typingShown, replied: !!replied, cleared: box.value === '' });
