from test import execute_query 
import threading


while True:
    # print(dir(VectorIndexRetriever))
    query = input("Enter query: ")
    


    if query == "exit":
        print("Exiting...")
        break

    
    result_holder = [None]

    
    query_thread = threading.Thread(target=execute_query, args=( query, result_holder))
    query_thread.start()

    # Wait for the query to finish or timeout after 5 seconds
    query_thread.join(timeout=5)

    # If the thread is still alive after the timeout, we consider it as a timeout
    if query_thread.is_alive():
        print("Query timed out, returning null.")
        result = None
    else:
        result = result_holder[0]

    print(result)

