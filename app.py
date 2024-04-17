import os
import requests
import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from requests.auth import HTTPBasicAuth
from langchain.vectorstores import FAISS
from langchain.llms import HuggingFaceHub
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains import ConversationalRetrievalChain
from htmlTemplates import css, bot_template, user_template
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceInstructEmbeddings
def get_zendesk_ticket(sub_domain, username, password):
    url = f"https://{sub_domain}.zendesk.com/api/v2/tickets"
    auth = HTTPBasicAuth(username, password)
    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        tickets_data = response.json()['tickets']

        tickets_info = {
            ticket['id']: {
                'title': ticket['subject'],
                'description': ticket['description']
            }
            for ticket in tickets_data
        }

        return tickets_info
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return {}
def get_vectorstore(raw_text):
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(texts=raw_text, embedding=embeddings)
    return vectorstore

def get_conversation_chain(vectorstore):
    llm = ChatOpenAI()
    memory = ConversationBufferMemory(
        memory_key=f'chat_history', return_messages=True)
    memory.clear()
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversation_chain

def handle_userinput(user_question):
    response = st.session_state.conversation({'question': user_question})
    st.session_state.chat_history = response[f'chat_history']

    for i, message in enumerate(st.session_state.chat_history):
        if i % 2 == 0:
            st.write(user_template.replace(
                "{{MSG}}", message.content), unsafe_allow_html=True)
        else:
            st.write(bot_template.replace(
                "{{MSG}}", message.content), unsafe_allow_html=True)

def get_text_chunks(text):
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks

def main():
    load_dotenv()
    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None
    if "selected_ticket_id" not in st.session_state:
        st.session_state.selected_ticket_id = None
    st.set_page_config(page_title="Chat with Zendesk AI",
                       page_icon=":robot_face:")
    st.write(css, unsafe_allow_html=True)
    tickets = get_zendesk_ticket(os.getenv('ZENDESK_SUB_DOMAIN'), os.getenv('ZENDESK_USERNAME'), os.getenv('ZENDESK_PASSWORD'))
    ticket_options = [f"{ticket_id} : {info['title']}" for ticket_id, info in tickets.items()]
    option = st.selectbox('Which ticket do you want to ask about?', ticket_options)
    selected_ticket_id = option.split(" : ")[0]
    selected_ticket = tickets[int(selected_ticket_id)]
    raw_text = selected_ticket['title'] + " : " + selected_ticket['description']

    if option is not None and st.session_state['selected_ticket_id'] != selected_ticket_id:
        st.session_state['selected_ticket_id'] = selected_ticket_id
        # text_chunks = get_text_chunks(raw_text)
        vectorstore = get_vectorstore([raw_text])
        st.session_state.conversation = get_conversation_chain(vectorstore)
    st.write('Title:', selected_ticket['title'])
    st.write('Description:', selected_ticket['description'])
    st.header("Chat with Zendesk AI :robot_face:")
    user_question = st.text_input("Ask a question about your tickets:")
    if user_question:
        handle_userinput(user_question)


if __name__ == '__main__':
    main()
