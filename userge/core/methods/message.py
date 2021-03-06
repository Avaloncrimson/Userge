# Copyright (C) 2020 by UsergeTeam@Github, < https://github.com/UsergeTeam >.
#
# This file is part of < https://github.com/UsergeTeam/Userge > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/uaudith/Userge/blob/master/LICENSE >
#
# All rights reserved.

__all__ = ['Message']

import re
import os
import asyncio
from typing import List, Dict, Union, Optional, Sequence

import aiofiles
from pyrogram import Client as RawClient, Message as RawMessage, InlineKeyboardMarkup
from pyrogram.errors.exceptions import MessageAuthorRequired, MessageTooLong
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified, MessageIdInvalid

from userge import logging, Config
from . import logger

_CANCEL_LIST: List[int] = []
_ERROR_MSG_DELETE_TIMEOUT = 5
_ERROR_STRING = "**ERROR**: `{}`"

_LOG = logging.getLogger(__name__)
_LOG_STR = "<<<!  :::::  %s  :::::  !>>>"

class Message(RawMessage):
    """Modded Message Class For Userge"""
    def __init__(self,
                 client: RawClient,
                 message: RawMessage,
                 **kwargs: Union[str, bool]) -> None:
        super().__init__(client=client, **self._msg_to_dict(message))
        self.message_id: int
        self.reply_to_message: Optional[RawMessage]
        if self.reply_to_message:
            self.reply_to_message = self.__class__(self._client, self.reply_to_message)
        self._channel = logger.CLogger(client, __name__)
        self._filtered = False
        self._process_canceled = False
        self._filtered_input_str: str = ''
        self._flags: Dict[str, str] = {}
        self._kwargs = kwargs

    @property
    def input_str(self) -> str:
        """Returns the input string without command"""
        input_ = self.text
        if ' ' in input_:
            return str(input_.split(maxsplit=1)[1].strip())
        return ''

    @property
    def input_or_reply_str(self) -> str:
        """Returns the input string  or replied msg text without command"""
        input_ = self.input_str
        if not input_ and self.reply_to_message:
            input_ = (self.reply_to_message.text or '').strip()
        return input_

    @property
    def filtered_input_str(self) -> str:
        """Returns the filtered input string without command and flags"""
        self._filter()
        return self._filtered_input_str

    @property
    def flags(self) -> Dict[str, str]:
        """Returns all flags in input string as `Dict`"""
        self._filter()
        return self._flags

    @property
    def process_is_canceled(self) -> bool:
        """Returns True if process canceled"""
        if self.message_id in _CANCEL_LIST:
            _CANCEL_LIST.remove(self.message_id)
            self._process_canceled = True
        return self._process_canceled

    def cancel_the_process(self) -> None:
        """Set True to the self.process_is_canceled"""
        _CANCEL_LIST.append(self.message_id)

    @staticmethod
    def _msg_to_dict(message: RawMessage) -> Dict[str, object]:
        kwargs_ = vars(message)
        del message
        for key_ in ['_client', '_channel', '_filtered', '_process_canceled',
                     '_filtered_input_str', '_flags', '_kwargs']:
            if key_ in kwargs_:
                del kwargs_[key_]
        return kwargs_

    def _filter(self) -> None:
        if not self._filtered:
            prefix = str(self._kwargs.get('prefix', '-'))
            del_pre = bool(self._kwargs.get('del_pre', False))
            input_str = self.input_str
            for i in input_str.strip().split():
                match = re.match(f"({prefix}[a-zA-Z]+)([0-9]*)$", i)
                if match:
                    items: Sequence[str] = match.groups()
                    self._flags[items[0].lstrip(prefix).lower() if del_pre \
                        else items[0].lower()] = items[1] or ''
                else:
                    self._filtered_input_str += ' ' + i
            self._filtered_input_str = self._filtered_input_str.strip()
            _LOG.debug(
                _LOG_STR,
                f"Filtered Input String => [ {self._filtered_input_str}, {self._flags} ]")
            self._filtered = True

    async def send_as_file(self,
                           text: str,
                           filename: str = "output.txt",
                           caption: str = '',
                           log: Union[bool, str] = False,
                           delete_message: bool = True) -> 'Message':
        """\nYou can send large outputs as file

        Example:
                message.send_as_file(text="hello")

        Parameters:
            text (``str``):
                Text of the message to be sent.

            filename (``str``, *optional*):
                file_name for output file.

            caption (``str``, *optional*):
                caption for output file.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            delete_message (``bool``, *optional*):
                If ``True``, the message will be deleted
                after sending the file.

        Returns:
            On success, the sent Message is returned.
        """
        async with aiofiles.open(filename, "w+", encoding="utf8") as out_file:
            await out_file.write(text)
        reply_to_id = self.reply_to_message.message_id if self.reply_to_message \
            else self.message_id
        _LOG.debug(_LOG_STR, f"Uploading {filename} To Telegram")
        msg = await self._client.send_document(chat_id=self.chat.id,
                                               document=filename,
                                               caption=caption,
                                               disable_notification=True,
                                               reply_to_message_id=reply_to_id)
        os.remove(filename)
        if log:
            if isinstance(log, str):
                self._channel.update(log)
            await self._channel.fwd_msg(msg)
        if delete_message:
            asyncio.create_task(self.delete())
        return Message(self._client, msg)

    async def reply(self,
                    text: str,
                    del_in: int = -1,
                    log: Union[bool, str] = False,
                    quote: Optional[bool] = None,
                    parse_mode: Union[str, object] = object,
                    disable_web_page_preview: Optional[bool] = None,
                    disable_notification: Optional[bool] = None,
                    reply_to_message_id: Optional[int] = None,
                    reply_markup: InlineKeyboardMarkup = None) -> Union['Message', bool]:
        """\nExample:
                message.reply("hello")

        Parameters:
            text (``str``):
                Text of the message to be sent.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as
                a reply to this message.
                If *reply_to_message_id* is passed,
                this parameter will be ignored.
                Defaults to ``True`` in group chats
                and ``False`` in private chats.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using both
                Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            reply_to_message_id (``int``, *optional*):
                If the message is a reply, ID of the original message.

            reply_markup (:obj:`InlineKeyboardMarkup`
            | :obj:`ReplyKeyboardMarkup` | :obj:`ReplyKeyboardRemove`
            | :obj:`ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard,
                custom reply keyboard,
                instructions to remove reply keyboard or to
                force a reply from the user.

        Returns:
            On success, the sent Message or True is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != "private"
        if reply_to_message_id is None and quote:
            reply_to_message_id = self.message_id
        msg = await self._client.send_message(chat_id=self.chat.id,
                                              text=text,
                                              parse_mode=parse_mode,
                                              disable_web_page_preview=disable_web_page_preview,
                                              disable_notification=disable_notification,
                                              reply_to_message_id=reply_to_message_id,
                                              reply_markup=reply_markup)
        if log:
            if isinstance(log, str):
                self._channel.update(log)
            await self._channel.fwd_msg(msg)
        del_in = del_in or Config.MSG_DELETE_TIMEOUT
        if del_in > 0:
            await asyncio.sleep(del_in)
            return bool(await msg.delete())
        return Message(self._client, msg)

    reply_text = reply

    async def edit(self,
                   text: str,
                   del_in: int = -1,
                   log: Union[bool, str] = False,
                   sudo: bool = True,
                   parse_mode: Union[str, object] = object,
                   disable_web_page_preview: Optional[bool] = None,
                   reply_markup: InlineKeyboardMarkup = None) -> Union['Message', bool]:
        """\nExample:
                message.edit_text("hello")

        Parameters:
            text (``str``):
                New text of the message.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            sudo (``bool``, *optional*):
                If ``True``, sudo users supported.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using
                both Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            reply_markup (:obj:`InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

        Returns:
            On success, the edited
            :obj:`Message` or True is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        try:
            msg_ = await self._client.edit_message_text(chat_id=self.chat.id,
                                                        message_id=self.message_id,
                                                        text=text,
                                                        parse_mode=parse_mode,
                                                        disable_web_page_preview=disable_web_page_preview,
                                                        reply_markup=reply_markup)
        except (MessageAuthorRequired, MessageIdInvalid) as m_er:
            if sudo:
                msg = await self.reply(text=text,
                                       del_in=del_in,
                                       log=log,
                                       parse_mode=parse_mode,
                                       disable_web_page_preview=disable_web_page_preview,
                                       reply_markup=reply_markup)
                if isinstance(msg, Message):
                    self.message_id = msg.message_id
                return msg
            raise m_er
        else:
            if log:
                if isinstance(log, str):
                    self._channel.update(log)
                await self._channel.fwd_msg(msg_)
            del_in = del_in or Config.MSG_DELETE_TIMEOUT
            if del_in > 0:
                await asyncio.sleep(del_in)
                return bool(await msg_.delete())
            return Message(self._client, msg_)

    edit_text = edit

    async def force_edit(self,
                         text: str,
                         del_in: int = -1,
                         log: Union[bool, str] = False,
                         parse_mode: Union[str, object] = object,
                         disable_web_page_preview: Optional[bool] = None,
                         reply_markup: InlineKeyboardMarkup = None,
                         **kwargs) -> Union['Message', bool]:
        """\nThis will first try to message.edit.
        If it raise MessageAuthorRequired or
        MessageIdInvalid error, run message.reply.

        Example:
                message.force_edit(text='force_edit', del_in=3)

        Parameters:
            text (``str``):
                New text of the message.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using both
                Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            reply_markup (:obj:`InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

            **kwargs (for message.reply)

        Returns:
            On success, the edited or replied
            :obj:`Message` or True is returned.
        """
        try:
            return await self.edit(text=text,
                                   del_in=del_in,
                                   log=log,
                                   sudo=False,
                                   parse_mode=parse_mode,
                                   disable_web_page_preview=disable_web_page_preview,
                                   reply_markup=reply_markup)
        except (MessageAuthorRequired, MessageIdInvalid):
            return await self.reply(text=text,
                                    del_in=del_in,
                                    log=log,
                                    parse_mode=parse_mode,
                                    disable_web_page_preview=disable_web_page_preview,
                                    reply_markup=reply_markup,
                                    **kwargs)

    async def err(self,
                  text: str,
                  del_in: int = -1,
                  log: Union[bool, str] = False,
                  sudo: bool = True,
                  parse_mode: Union[str, object] = object,
                  disable_web_page_preview: Optional[bool] = None,
                  reply_markup: InlineKeyboardMarkup = None) -> Union['Message', bool]:
        """\nYou can send error messages using this method

        Example:
                message.err(text='error', del_in=3)
        Parameters:
            text (``str``):
                New text of the message.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            sudo (``bool``, *optional*):
                If ``True``, sudo users supported.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using
                both Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            reply_markup (:obj:`InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

        Returns:
            On success, the edited
            :obj:`Message` or True is returned.
        """
        del_in = del_in if del_in > 0 \
            else _ERROR_MSG_DELETE_TIMEOUT
        return await self.edit(text=_ERROR_STRING.format(text),
                               del_in=del_in,
                               log=log,
                               sudo=sudo,
                               parse_mode=parse_mode,
                               disable_web_page_preview=disable_web_page_preview,
                               reply_markup=reply_markup)

    async def force_err(self,
                        text: str,
                        del_in: int = -1,
                        log: Union[bool, str] = False,
                        parse_mode: Union[str, object] = object,
                        disable_web_page_preview: Optional[bool] = None,
                        reply_markup: InlineKeyboardMarkup = None,
                        **kwargs) -> Union['Message', bool]:
        """\nThis will first try to message.edit.
        If it raise MessageAuthorRequired or
        MessageIdInvalid error, run message.reply.

        Example:
                message.force_err(text='force_err', del_in=3)

        Parameters:
            text (``str``):
                New text of the message.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using
                both Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            reply_markup (:obj:`InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

            **kwargs (for message.reply)

        Returns:
            On success, the edited or replied
            :obj:`Message` or True is returned.
        """
        del_in = del_in if del_in > 0 \
            else _ERROR_MSG_DELETE_TIMEOUT
        return await self.force_edit(text=_ERROR_STRING.format(text),
                                     del_in=del_in,
                                     log=log,
                                     parse_mode=parse_mode,
                                     disable_web_page_preview=disable_web_page_preview,
                                     reply_markup=reply_markup,
                                     **kwargs)

    async def try_to_edit(self,
                          text: str,
                          del_in: int = -1,
                          log: Union[bool, str] = False,
                          sudo: bool = True,
                          parse_mode: Union[str, object] = object,
                          disable_web_page_preview: Optional[bool] = None,
                          reply_markup: InlineKeyboardMarkup = None) -> Union['Message', bool]:
        """\nThis will first try to message.edit.
        If it raise MessageNotModified error,
        just pass it.

        Example:
                message.try_to_edit("hello")

        Parameters:
            text (``str``):
                New text of the message.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            sudo (``bool``, *optional*):
                If ``True``, sudo users supported.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using
                both Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            reply_markup (:obj:`InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

        Returns:
            On success, the edited
            :obj:`Message` or True is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        try:
            return await self.edit(text=text,
                                   del_in=del_in,
                                   log=log,
                                   sudo=sudo,
                                   parse_mode=parse_mode,
                                   disable_web_page_preview=disable_web_page_preview,
                                   reply_markup=reply_markup)
        except MessageNotModified:
            return False

    async def edit_or_send_as_file(self,
                                   text: str,
                                   del_in: int = -1,
                                   log: Union[bool, str] = False,
                                   sudo: bool = True,
                                   parse_mode: Union[str, object] = object,
                                   disable_web_page_preview: Optional[bool] = None,
                                   reply_markup: InlineKeyboardMarkup = None,
                                   **kwargs) -> Union['Message', bool]:
        """\nThis will first try to message.edit.
        If it raise MessageTooLong error,
        run message.send_as_file.

        Example:
                message.edit_or_send_as_file("some huge text")

        Parameters:
            text (``str``):
                New text of the message.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            sudo (``bool``, *optional*):
                If ``True``, sudo users supported.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using both
                Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            reply_markup (:obj:`InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

            **kwargs (for message.send_as_file)

        Returns:
            On success, the edited
            :obj:`Message` or True is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        try:
            return await self.edit(text=text,
                                   del_in=del_in,
                                   log=log,
                                   sudo=sudo,
                                   parse_mode=parse_mode,
                                   disable_web_page_preview=disable_web_page_preview,
                                   reply_markup=reply_markup)
        except (MessageTooLong, OSError):
            return await self.send_as_file(text=text, log=log, **kwargs)

    async def reply_or_send_as_file(self,
                                    text: str,
                                    del_in: int = -1,
                                    log: Union[bool, str] = False,
                                    quote: Optional[bool] = None,
                                    parse_mode: Union[str, object] = object,
                                    disable_web_page_preview: Optional[bool] = None,
                                    disable_notification: Optional[bool] = None,
                                    reply_to_message_id: Optional[int] = None,
                                    reply_markup: InlineKeyboardMarkup = None,
                                    **kwargs) -> Union['Message', bool]:
        """\nThis will first try to message.reply.
        If it raise MessageTooLong error,
        run message.send_as_file.

        Example:
                message.reply_or_send_as_file("some huge text")

        Parameters:
            text (``str``):
                Text of the message to be sent.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be forwarded
                to the log channel.
                If ``str``, the logger name will be updated.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent
                as a reply to this message.
                If *reply_to_message_id* is passed,
                this parameter will be ignored.
                Defaults to ``True`` in group chats
                and ``False`` in private chats.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using
                both Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            reply_to_message_id (``int``, *optional*):
                If the message is a reply, ID of the
                original message.

            reply_markup (:obj:`InlineKeyboardMarkup`
            | :obj:`ReplyKeyboardMarkup` | :obj:`ReplyKeyboardRemove`
            | :obj:`ForceReply`, *optional*):
                Additional interface options. An object for an
                inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard
                or to force a reply from the user.

            **kwargs (for message.send_as_file)

        Returns:
            On success, the sent Message or True is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        try:
            return await self.reply(text=text,
                                    del_in=del_in,
                                    log=log,
                                    quote=quote,
                                    parse_mode=parse_mode,
                                    disable_web_page_preview=disable_web_page_preview,
                                    disable_notification=disable_notification,
                                    reply_to_message_id=reply_to_message_id,
                                    reply_markup=reply_markup)
        except MessageTooLong:
            return await self.send_as_file(text=text, log=log, **kwargs)

    async def force_edit_or_send_as_file(self,
                                         text: str,
                                         del_in: int = -1,
                                         log: Union[bool, str] = False,
                                         parse_mode: Union[str, object] = object,
                                         disable_web_page_preview: Optional[bool] = None,
                                         reply_markup: InlineKeyboardMarkup = None,
                                         **kwargs) -> Union['Message', bool]:
        """\nThis will first try to message.edit_or_send_as_file.
        If it raise MessageAuthorRequired
        or MessageIdInvalid error, run message.reply_or_send_as_file.

        Example:
                message.force_edit_or_send_as_file("some huge text")

        Parameters:
            text (``str``):
                New text of the message.

            del_in (``int``):
                Time in Seconds for delete that message.

            log (``bool`` | ``str``, *optional*):
                If ``True``, the message will be
                forwarded to the log channel.
                If ``str``, the logger name will be updated.

            parse_mode (``str``, *optional*):
                By default, texts are parsed using
                both Markdown and HTML styles.
                You can combine both syntaxes together.
                Pass "markdown" or "md" to enable
                Markdown-style parsing only.
                Pass "html" to enable HTML-style parsing only.
                Pass None to completely disable style parsing.

            disable_web_page_preview (``bool``, *optional*):
                Disables link previews for links in this message.

            reply_markup (:obj:`InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

            **kwargs (for message.reply and message.send_as_file)

        Returns:
            On success, the edited or replied
            :obj:`Message` or True is returned.
        """
        try:
            return await self.edit_or_send_as_file(text=text,
                                                   del_in=del_in,
                                                   log=log,
                                                   sudo=False,
                                                   parse_mode=parse_mode,
                                                   disable_web_page_preview=disable_web_page_preview,
                                                   reply_markup=reply_markup,
                                                   **kwargs)
        except (MessageAuthorRequired, MessageIdInvalid):
            return await self.reply_or_send_as_file(text=text,
                                                    del_in=del_in,
                                                    log=log,
                                                    parse_mode=parse_mode,
                                                    disable_web_page_preview=disable_web_page_preview,
                                                    reply_markup=reply_markup,
                                                    **kwargs)
