import React from 'react';
import { ChatMessage as ChatMessageType } from '../../types/chat';
import { ChatMessage } from './ChatMessage';

interface ChatMessageListProps {
  messages: ChatMessageType[];
  onToggleThinking: (id: string) => void;
}

export const ChatMessageList: React.FC<ChatMessageListProps> = ({ messages, onToggleThinking }) => (
  <>
    {messages.map((message) => {
      const isEmptyAssistant =
        message.role === 'assistant' &&
        message.content.trim().length === 0 &&
        !message.thinking;

      return isEmptyAssistant ? null : (
        <ChatMessage key={message.id} message={message} onToggleThinking={onToggleThinking} />
      );
    })}
  </>
);
