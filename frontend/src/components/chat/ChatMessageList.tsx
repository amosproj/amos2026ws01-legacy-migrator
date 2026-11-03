import React from 'react';
import { ChatMessage as ChatMessageType } from '../../types/chat';
import { ChatMessage } from './ChatMessage';

interface ChatMessageListProps {
  messages: ChatMessageType[];
}

export const ChatMessageList: React.FC<ChatMessageListProps> = ({ messages }) => (
  <>
    {messages.map((message) => {
      const isEmptyAssistant = message.role === 'assistant' && message.content.trim().length === 0;

      return isEmptyAssistant ? null : (
        <ChatMessage key={message.id} message={message} />
      );
    })}
  </>
);
