"""Module contains the class to construct fuzzyfinder prompt."""
from typing import Any, Callable, Dict, List, Literal, Tuple, Union

from prompt_toolkit.application.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters.base import Condition
from prompt_toolkit.filters.cli import IsDone
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Float,
    FloatContainer,
    HSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension, LayoutDimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.processors import AfterInput, BeforeInput
from prompt_toolkit.validation import ValidationError, Validator
from prompt_toolkit.widgets.base import Frame

from InquirerPy.base import BaseSimplePrompt, FakeDocument, InquirerPyUIControl
from InquirerPy.enum import INQUIRERPY_POINTER_SEQUENCE
from InquirerPy.exceptions import InvalidArgument
from InquirerPy.prompts.fuzzy.fzy import fuzzy_match_py
from InquirerPy.separator import Separator
from InquirerPy.utils import calculate_height


class InquirerPyFuzzyControl(InquirerPyUIControl):
    """A UIControl element intended to be used by `prompt_toolkit` Window class.

    This UIControl is for listing the available choices based on filtering.
    The actual input buffer will be handled by a separate BufferControl.

    :param choices: list of choices to display
    :type choices: List[Any]
    :param default: default value, move selected_choice_index
    :type default: Any
    :param pointer: pointer symbol
    :type pointer: str
    :param marker: marker symbol for the selected choice in the case of multiselect
    :type marker: str
    :param current_text: current buffer text
    :type current_text: Callable[[], str]
    """

    def __init__(
        self,
        choices: List[Any],
        default: Any,
        pointer: str,
        marker: str,
        current_text: Callable[[], str],
    ) -> None:
        """Construct UIControl and initialise choices."""
        self._pointer = pointer
        self._marker = marker
        super().__init__(choices, default)
        self._current_text = current_text

        for index, choice in enumerate(self.choices):
            if isinstance(choice["value"], Separator):
                raise InvalidArgument("fuzzy type prompt does not accept Separator.")
            choice["enabled"] = False
            choice["index"] = index

        self._filtered_choices = self.choices
        self._filtered_indices = []

    def _get_hover_text(self, choice, indices) -> List[Tuple[str, str]]:
        """Get the current highlighted line of text in `FormattedText`.

        If in the middle of filtering, loop through the char and color
        indices matched char into `class:fuzzy_match`.

        :return: list of formatted text
        :rtype: List[Tuple[str, str]]
        """
        display_choices = []
        display_choices.append(("class:pointer", self._pointer))
        display_choices.append(
            ("class:fuzzy_marker", self._marker if choice["enabled"] else " ")
        )
        display_choices.append(("[SetCursorPosition]", ""))
        if not indices:
            display_choices.append(("class:pointer", choice["name"]))
        else:
            indices = set(indices)
            for index, char in enumerate(choice["name"]):
                if index in indices:
                    display_choices.append(("class:fuzzy_match", char))
                else:
                    display_choices.append(("class:pointer", char))
        return display_choices

    def _get_normal_text(self, choice, indices) -> List[Tuple[str, str]]:
        """Get the line of text in `FormattedText`.

        If in the middle of filtering, loop through the char and color
        indices matched char into `class:fuzzy_match`.

        Calculate spaces of pointer to make the choice equally align.

        :return: list of formatted text
        :rtype: List[Tuple[str, str]]
        """
        display_choices = []
        display_choices.append(("class:pointer", len(self._pointer) * " "))
        display_choices.append(
            (
                "class:fuzzy_marker",
                self._marker if choice["enabled"] else " ",
            )
        )
        if not indices:
            display_choices.append(("", choice["name"]))
        else:
            indices = set(indices)
            for index, char in enumerate(choice["name"]):
                if index in indices:
                    display_choices.append(("class:fuzzy_match", char))
                else:
                    display_choices.append(("", char))
        return display_choices

    def _get_formatted_choices(self) -> List[Tuple[str, str]]:
        """Get all available choices in formatted text format.

        Overriding this method because `self.choice` will be the
        full choice list. Using `self.filtered_choice` to get
        a list of choice based on current_text.

        :return: a list of formatted choices
        :rtype: List[Tuple[str, str]]
        """
        display_choices = []

        for index, choice in enumerate(self._filtered_choices):
            if index == self.selected_choice_index:
                try:
                    display_choices += self._get_hover_text(
                        choice,
                        self._filtered_indices[index],
                    )
                except IndexError:
                    display_choices += self._get_hover_text(choice, None)
            else:
                try:
                    display_choices += self._get_normal_text(
                        choice,
                        self._filtered_indices[index],
                    )
                except IndexError:
                    display_choices += self._get_normal_text(choice, None)
            display_choices.append(("", "\n"))
        if display_choices:
            display_choices.pop()
        return display_choices

    def filter_choices(self) -> None:
        """Call to filter choices using fzy fuzzy match.

        Making it callable so that it can be called duing `prompt_toolkit` buffer
        event `on_text_changed`. This allows to get the `self.selected_choice_index`
        a more realtime and accurate adjustment.
        """
        if not self._current_text():
            self._filtered_choices = self.choices
        else:
            indices, choices = fuzzy_match_py(self._current_text(), self.choices)
            self._filtered_choices = choices
            self._filtered_indices = indices

    @property
    def selection(self) -> Dict[str, Any]:
        """Override this value since `self.choice` does not indicate the choice displayed.

        `self.filtered_choice` is the up to date choice displayed.

        :return: a dictionary of name and value for the current pointed choice
        :rtype: Dict[str, Any]
        """
        return self._filtered_choices[self.selected_choice_index]

    @property
    def choice_count(self) -> int:
        """Get the filtered choice count.

        :return: total count of choices
        :rtype: int
        """
        return len(self._filtered_choices)


class FuzzyPrompt(BaseSimplePrompt):
    """A filter prompt that allows user to input value.

    Filters the result using fuzzy finding. The fuzzy finding logic
    is contains in the file fzy.py which is copied from `vim-clap`
    python provider.

    :param message: message to display to the user
    :type message: str
    :param choices: list of choices available to select
    :type choices: List[Any]
    :param default: default value
    :type default: Any
    :param pointer: pointer symbol
    :type pointer: str
    :param style: style dict to apply
    :type style: Dict[str, str]
    :param editing_mode: keybinding mode
    :type editing_mode: Literal["default", "vim", "emacs"]
    :param qmark: question mark symbol
    :type qmark: str
    :param transformer: transform the result to output, this is only visual effect
    :type transformer: Callable
    :param instruction: instruction to display after the message
    :type instruction: str
    :param multiselect: enable multi selection of the choices
    :type multiselect: bool
    :param prompt: prompt symbol for buffer
    :type prompt: str
    :param marker: marker symbol for the selected choice in the case of multiselect
    :type marker: str
    :param border: enable border around the fuzzy prompt
    :type border: bool
    :param info: display info as virtual text after input
    :type info: bool
    :param height: preferred height of the choice window
    :type height: Union[str, int]
    :param max_height: max height choice window should reach
    :type max_height: Union[str, int]
    :param validate: a callable or Validator instance to validate user selection
    :type validate: Union[Callable[[str], bool], Validator]
    :param invalid_message: message to display when input is invalid
    :type invalid_message: str
    """

    def __init__(
        self,
        message: str,
        choices: List[Any],
        default: Any = None,
        pointer: str = INQUIRERPY_POINTER_SEQUENCE,
        style: Dict[str, str] = {},
        editing_mode: Literal["default", "vim", "emacs"] = "default",
        qmark: str = "?",
        transformer: Callable = None,
        instruction: str = "",
        multiselect: bool = False,
        prompt: str = INQUIRERPY_POINTER_SEQUENCE,
        marker: str = INQUIRERPY_POINTER_SEQUENCE,
        border: bool = True,
        info: bool = True,
        height: Union[str, int] = None,
        max_height: Union[str, int] = None,
        validate: Union[Callable[[str], bool], Validator] = None,
        invalid_message: str = "Invalid input",
    ) -> None:
        """Initialise the layout and create Application.

        The Application have mainly 3 layers.
        1. question
        2. input
        3. choices

        The content of choices content_control is bounded by the input buffer content_control
        on_text_changed event.

        Once Enter is pressed, hide both input buffer and choices buffer as well as
        updating the question buffer with user selection.
        """
        self._instruction = instruction
        self._multiselect = multiselect
        self._prompt = prompt
        self._border = border
        self._info = info
        self._invalid_message = invalid_message

        super().__init__(
            message=message,
            style=style,
            editing_mode=editing_mode,
            qmark=qmark,
            transformer=transformer,
            validate=validate,
            invalid_message=invalid_message,
        )
        self._content_control = InquirerPyFuzzyControl(
            choices=choices,
            default=default,
            pointer=pointer,
            marker=marker,
            current_text=self._get_current_text,
        )

        @Condition
        def is_multiselect() -> bool:
            return self._multiselect

        @Condition
        def is_invalid() -> bool:
            return self._invalid

        self._buffer = Buffer(on_text_changed=self._on_text_changed)
        message_window = Window(
            height=LayoutDimension.exact(1),
            content=FormattedTextControl(self._get_prompt_message, show_cursor=False),
        )
        input_window = Window(
            height=LayoutDimension.exact(1),
            content=BufferControl(
                self._buffer,
                [
                    AfterInput(self._generate_after_input),
                    BeforeInput(self._generate_before_input),
                ],
            ),
        )
        dimmension_height, dimmension_max_height = calculate_height(
            height, max_height, offset=2
        )
        choice_height_dimmension = Dimension(
            max=dimmension_max_height, preferred=dimmension_height
        )

        choice_window = Window(
            content=self.content_control, height=choice_height_dimmension
        )
        main_content_window = HSplit([input_window, choice_window])
        if self._border:
            main_content_window = Frame(main_content_window)
        self._layout = Layout(
            HSplit(
                [
                    message_window,
                    ConditionalContainer(
                        FloatContainer(
                            content=main_content_window,
                            floats=[
                                Float(
                                    ConditionalContainer(
                                        Window(
                                            FormattedTextControl(
                                                [
                                                    (
                                                        "class:validation-toolbar",
                                                        self._invalid_message,
                                                    )
                                                ]
                                            ),
                                            dont_extend_height=True,
                                        ),
                                        filter=is_invalid,
                                    ),
                                    bottom=1 if self._border else 0,
                                    left=1 if self._border else 0,
                                )
                            ],
                        ),
                        filter=~IsDone(),
                    ),
                ]
            )
        )
        self._layout.focus(input_window)

        @self._register_kb(Keys.Enter)
        def _(event):
            self._handle_enter(event)

        @self._register_kb(Keys.Tab, filter=is_multiselect)
        def _(event):
            self._handle_tab()
            self._handle_down()

        @self._register_kb(Keys.BackTab, filter=is_multiselect)
        def _(event):
            self._handle_tab()
            self._handle_up()

        @self._register_kb(Keys.Down)
        @self._register_kb("c-n")
        def _(event):
            self._handle_down()

        @self._register_kb(Keys.Up)
        @self._register_kb("c-p")
        def _(event):
            self._handle_up()

        @self._register_kb("escape", "a", filter=is_multiselect)
        def _(event) -> None:
            self._toggle_all(True)

        @self._register_kb("escape", "r", filter=is_multiselect)
        def _(event) -> None:
            self._toggle_all()

        self._application = Application(
            layout=self._layout,
            style=self.question_style,
            key_bindings=self.kb,
            editing_mode=self.editing_mode,
        )

    def _toggle_all(self, value: bool = None) -> None:
        """Toggle all choice `enabled` status.

        :param value: sepcify a value to toggle
        :type value: bool
        """
        for choice in self.content_control.choices:
            if isinstance(choice["value"], Separator):
                continue
            choice["enabled"] = value if value else not choice["enabled"]

    def _generate_after_input(self) -> List[Tuple[str, str]]:
        """Virtual text displayed after the user input."""
        display_message = []
        if self._info:
            display_message.append(("", "  "))
            display_message.append(
                (
                    "class:fuzzy_info",
                    "%s/%s"
                    % (
                        self.content_control.choice_count,
                        len(self.content_control.choices),
                    ),
                )
            )
            if self._multiselect:
                display_message.append(
                    ("class:fuzzy_info", " (%s)" % len(self.selected_choices))
                )
        return display_message

    def _generate_before_input(self) -> List[Tuple[str, str]]:
        """Display prompt symbol as virtual text before user input."""
        display_message = []
        display_message.append(("class:fuzzy_prompt", "%s " % self._prompt))
        return display_message

    def _on_text_changed(self, buffer) -> None:
        """Handle buffer text change event.

        Run fuzzy filter in asyncio, each line process
        concurrently via asyncio.gather.

        1. Run a new filter on all choices.
        2. Re-calculate current selected_choice_index
            if it exceeds the total filtered_choice.
        3. Avoid selected_choice_index less than zero,
            this fix the issue of cursor lose when:
            choice -> empty choice -> choice
        """
        if self._invalid:
            self._invalid = False
        self.content_control.filter_choices()

        if (
            self.content_control.selected_choice_index
            > self.content_control.choice_count - 1
        ):
            self.content_control.selected_choice_index = (
                self.content_control.choice_count - 1
            )
        if self.content_control.selected_choice_index == -1:
            self.content_control.selected_choice_index = 0

    def _handle_down(self) -> None:
        """Move down."""
        self.content_control.selected_choice_index = (
            self.content_control.selected_choice_index + 1
        ) % self.content_control.choice_count

    def _handle_up(self) -> None:
        """Move up."""
        self.content_control.selected_choice_index = (
            self.content_control.selected_choice_index - 1
        ) % self.content_control.choice_count

    def _handle_tab(self) -> None:
        """Handle tab event, alter the `selected` state of the choice."""
        current_selected_index = self.content_control.selection["index"]
        self.content_control.choices[current_selected_index][
            "enabled"
        ] = not self.content_control.choices[current_selected_index]["enabled"]

    def _handle_enter(self, event) -> None:
        """Handle enter event.

        Validate the result first.

        In multiselect scenario, if no TAB is entered, then capture the current
        highlighted choice and return the value in a list.
        Otherwise, return all TAB choices as a list.

        In normal scenario, reutrn the current highlighted choice.

        If current UI contains no choice due to filter, return None.
        """
        try:
            fake_document = FakeDocument(self.result_value)
            self.validator.validate(fake_document)  # type: ignore
        except ValidationError:
            self._invalid = True
            return
        try:
            if self._multiselect:
                self.status["answered"] = True
                if not self.selected_choices:
                    self.status["result"] = [self.content_control.selection["name"]]
                    event.app.exit(result=[self.content_control.selection["value"]])
                else:
                    self.status["result"] = self.result_name
                    event.app.exit(result=self.result_value)
            else:
                self.status["answered"] = True
                self.status["result"] = self.content_control.selection["name"]
                event.app.exit(result=self.content_control.selection["value"])
        except IndexError:
            self.status["answered"] = True
            self.status["result"] = None if not self._multiselect else []
            event.app.exit(result=None if not self._multiselect else [])

    @property
    def selected_choices(self) -> List[Dict[str, Any]]:
        """Get all user enabled choices."""
        return list(
            filter(lambda choice: choice["enabled"], self.content_control.choices)
        )

    @property
    def result_name(self) -> Any:
        """Get the result name of the application.

        In multiselect scenario, return result as a list.
        """
        if self._multiselect:
            return [choice["name"] for choice in self.selected_choices]
        else:
            return self.content_control.selection["name"]

    @property
    def result_value(self) -> Any:
        """Get the result value of the application.

        In multiselect scenario, return result as a list.
        """
        if self._multiselect:
            return [choice["value"] for choice in self.selected_choices]
        else:
            return self.content_control.selection["value"]

    @property
    def content_control(self) -> InquirerPyFuzzyControl:
        """Get the choice content_control."""
        return self._content_control

    def _get_current_text(self) -> str:
        """Get current input buffer text."""
        return self._buffer.text

    def _get_prompt_message(self) -> List[Tuple[str, str]]:
        """Get the prompt message for FormattedTextControl.

        To be used by the first window in layout.

        :return: list of formatted text
        :rtype: List[Tuple[str, str]]
        """
        pre_answer = ("class:instruction", " %s" % self._instruction)
        post_answer = ("class:answer", " %s" % self.status["result"])
        return super()._get_prompt_message(pre_answer, post_answer)

    def execute(self) -> Any:
        """Execute the application and get the result."""
        return self._application.run()
