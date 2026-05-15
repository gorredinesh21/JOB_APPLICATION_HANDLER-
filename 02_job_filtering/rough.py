import os

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HUGGINGFACEHUB_API_TOKEN environment variable is required")

llm=HuggingFaceEndpoint(
    repo_id="meta-llama/Llama-3.1-8B-Instruct",
    task="text-generation",
    huggingfacehub_api_token=HF_TOKEN)

chat_model = ChatHuggingFace(llm=llm)


# Schema
class Weather(BaseModel):
    city: str = Field(description="Name of the city")
    temperature: int = Field(description="Temperature in Celsius")
    condition: str = Field(description="Weather condition like sunny, rainy")

parser = JsonOutputParser(pydantic_object=Weather)

template = PromptTemplate(
    template=(
        "Tell me the weather in {city}.\n"
        "Include a short natural language summary, then JSON:\n"
        "{format_instructions}"
    ),
    input_variables=["city"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)




chain=template | chat_model | parser 
final_result=chain.invoke({"city":"New York"})

print(final_result)
print(type(final_result))

if type(final_result)==list:
    for i in final_result:
        print(i['name'])
#print(final_result[0:]['name'])
