document.addEventListener('DOMContentLoaded', () => {
    const phoneInputContainer = document.getElementById('phone-input-container');
    const chatContainer = document.getElementById('chat-container');
    const chatBox = document.getElementById('chat-box');
    const phoneNumberInput = document.getElementById('phone-number');
    const startChatButton = document.getElementById('start-chat');
    const sendMessageButton = document.getElementById('send-message');
    const userMessageInput = document.getElementById('user-message');

    let phoneNumber = null;

    startChatButton.addEventListener('click', async () => {
        phoneNumber = phoneNumberInput.value.trim();
        if (!phoneNumber) return alert('Please enter a phone number');

        const response = await fetch('/ui_start-chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone_number: phoneNumber })
        });
        const data = await response.json();

        if (data.success) {
            phoneInputContainer.style.display = 'none';
            chatContainer.style.display = 'flex';
            chatBox.innerHTML = data.conversation.map(formatMessage).join('');
        } else {
            alert('Error starting chat');
        }
    });

    sendMessageButton.addEventListener('click', async () => {
        const userMessage = userMessageInput.value.trim();
        if (!userMessage) return;

        addMessageToChatBox(userMessage, 'user');
        userMessageInput.value = '';

        const response = await fetch('/ui_send-message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone_number: phoneNumber, message: userMessage })
        });
        const data = await response.json();

        if (data.success) {
            addMessageToChatBox(data.response, 'assistant');
        } else {
            alert('Error sending message');
        }
    });

    function formatMessage(message) {
        return `<div class="${message.role}">${message.text}</div>`;
    }

    function addMessageToChatBox(message, role) {
        const div = document.createElement('div');
        div.className = role;
        div.innerText = message;
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});
